"""Tests for stop_stream_wrapper: lock + compose run.

5/21 インシデント: orchestrator と既存 stop.plist が 07:05 に同時発火し
2 つの stop_stream.py が走った結果、翌日枠が 2 つ作成された (race condition)。
wrapper レベルで lock を取って 1 度に 1 プロセスだけ動くようにする。
"""
import os
import sys
from unittest.mock import patch

import pytest

project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(project_root, "scripts"))


def test_main_installs_15_minute_deadline():
    """A3: 7/7 wedge インシデント対策。15分でハングを強制終了する deadline。"""
    import stop_stream_wrapper as wrapper

    with patch("stop_stream_wrapper.install_deadline") as mock_install, \
         patch("stop_stream_wrapper.exclusive_run") as mock_lock, \
         patch("stop_stream_wrapper.subprocess.Popen") as mock_popen, \
         patch("stop_stream_wrapper.register_child"):
        mock_lock.return_value.__enter__.return_value = None
        mock_lock.return_value.__exit__.return_value = False
        mock_popen.return_value.wait.return_value = 0

        with pytest.raises(SystemExit):
            wrapper.main()

        mock_install.assert_called_once_with(15 * 60, "stop_stream_wrapper")


def test_main_skips_when_already_running():
    """別 trigger が既に動いていれば exit 0 で skip"""
    from rct.lockfile import AlreadyRunning

    import stop_stream_wrapper as wrapper

    with patch("stop_stream_wrapper.exclusive_run") as mock_lock, \
         patch("stop_stream_wrapper.subprocess.Popen") as mock_popen:
        mock_lock.return_value.__enter__.side_effect = AlreadyRunning("locked")
        mock_lock.return_value.__exit__.return_value = False

        with pytest.raises(SystemExit) as exc_info:
            wrapper.main()

        assert exc_info.value.code == 0
        mock_popen.assert_not_called()


def test_main_runs_compose_when_lock_available():
    """lock 取れたら docker compose run stop_stream.py を呼ぶ"""
    import stop_stream_wrapper as wrapper

    with patch("stop_stream_wrapper.exclusive_run") as mock_lock, \
         patch("stop_stream_wrapper.subprocess.Popen") as mock_popen, \
         patch("stop_stream_wrapper.register_child") as mock_register:
        mock_lock.return_value.__enter__.return_value = None
        mock_lock.return_value.__exit__.return_value = False
        mock_popen.return_value.wait.return_value = 0

        with pytest.raises(SystemExit) as exc_info:
            wrapper.main()

        assert exc_info.value.code == 0
        mock_popen.assert_called_once()
        called_args = mock_popen.call_args[0][0]
        assert "compose" in called_args
        assert "stop_stream.py" in called_args[-1]
        assert mock_popen.call_args[1].get("start_new_session") is True
        mock_register.assert_called_once_with(mock_popen.return_value)


def test_main_propagates_compose_returncode():
    """compose run が non-zero で終わったら同じ code で exit"""
    import stop_stream_wrapper as wrapper

    with patch("stop_stream_wrapper.exclusive_run") as mock_lock, \
         patch("stop_stream_wrapper.subprocess.Popen") as mock_popen, \
         patch("stop_stream_wrapper.register_child"), \
         patch("stop_stream_wrapper._check_stream_quality"):
        mock_lock.return_value.__enter__.return_value = None
        mock_lock.return_value.__exit__.return_value = False
        mock_popen.return_value.wait.return_value = 2

        with pytest.raises(SystemExit) as exc_info:
            wrapper.main()

        assert exc_info.value.code == 2


class TestCheckStreamQuality:
    """7/10 14:01 インシデント対策: compose run 完了後の OBS ログ品質チェック配線。"""

    def test_main_calls_quality_check_after_compose_run(self):
        """compose run 完了後、exit 前に品質チェックが呼ばれる。"""
        import stop_stream_wrapper as wrapper

        with patch("stop_stream_wrapper.exclusive_run") as mock_lock, \
             patch("stop_stream_wrapper.subprocess.Popen") as mock_popen, \
             patch("stop_stream_wrapper.register_child"), \
             patch("stop_stream_wrapper._check_stream_quality") as mock_check:
            mock_lock.return_value.__enter__.return_value = None
            mock_lock.return_value.__exit__.return_value = False
            mock_popen.return_value.wait.return_value = 0

            with pytest.raises(SystemExit):
                wrapper.main()

            mock_check.assert_called_once()

    def test_check_stream_quality_sends_alert_when_degraded(self):
        """品質 NG なら send_alert_email が呼ばれ、件名/本文に lag/skip % とログ名を含む。"""
        import stop_stream_wrapper as wrapper
        from rct.obs_quality import StreamQualityStats

        bad_stats = StreamQualityStats(
            rendering_lag_pct=25.9,
            rendering_lag_frames=3230,
            encoding_skip_pct=46.7,
            encoding_skip_frames=5795,
            encoding_total_frames=12420,
            total_frames=11735,
            source_log="2026-07-10 14-01-00.txt",
        )

        with patch("stop_stream_wrapper.get_latest_session_quality", return_value=bad_stats), \
             patch("stop_stream_wrapper.send_alert_email") as mock_alert:
            wrapper._check_stream_quality()

            mock_alert.assert_called_once()
            subject, body = mock_alert.call_args[0]
            assert "配信品質劣化検出" in subject
            assert "46.7" in body
            assert "25.9" in body
            assert "2026-07-10 14-01-00.txt" in body

    def test_check_stream_quality_no_alert_when_ok(self):
        """品質 OK なら send_alert_email は呼ばれない。"""
        import stop_stream_wrapper as wrapper
        from rct.obs_quality import StreamQualityStats

        good_stats = StreamQualityStats(
            rendering_lag_pct=0.1,
            rendering_lag_frames=12,
            encoding_skip_pct=0.0,
            encoding_skip_frames=5,
            encoding_total_frames=12420,
            total_frames=12420,
            source_log="2026-07-10 06-59-00.txt",
        )

        with patch("stop_stream_wrapper.get_latest_session_quality", return_value=good_stats), \
             patch("stop_stream_wrapper.send_alert_email") as mock_alert:
            wrapper._check_stream_quality()

            mock_alert.assert_not_called()

    def test_check_stream_quality_no_alert_when_no_stats(self):
        """統計が取得できない (ログ無し等) 場合は何もしない。"""
        import stop_stream_wrapper as wrapper

        with patch("stop_stream_wrapper.get_latest_session_quality", return_value=None), \
             patch("stop_stream_wrapper.send_alert_email") as mock_alert:
            wrapper._check_stream_quality()

            mock_alert.assert_not_called()

    def test_check_stream_quality_swallows_exceptions(self):
        """品質チェック自体が例外を投げても stop フローを止めない (握り潰さずログして継続)。"""
        import stop_stream_wrapper as wrapper

        with patch(
            "stop_stream_wrapper.get_latest_session_quality",
            side_effect=RuntimeError("boom"),
        ), patch("stop_stream_wrapper.send_alert_email") as mock_alert:
            wrapper._check_stream_quality()  # raises しないこと

            mock_alert.assert_not_called()
