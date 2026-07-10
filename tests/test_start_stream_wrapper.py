"""Tests for start_stream_wrapper: Docker daemon retry layer.

5/20 インシデント: prepare 遅延 → start 時に Docker daemon 未起動 →
`Cannot connect to the Docker daemon` で compose run 失敗。

wrapper が compose run 前に Docker daemon の応答を待つ。
"""
import os
import subprocess
import sys
from unittest.mock import patch

import pytest

project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(project_root, "scripts"))


def test_wait_for_docker_returns_true_immediately_when_ready():
    """Docker daemon が即応答 → True"""
    import start_stream_wrapper as wrapper

    with patch("start_stream_wrapper.subprocess.check_call") as mock_call, \
         patch("start_stream_wrapper.time.sleep") as mock_sleep:
        mock_call.return_value = 0

        assert wrapper.wait_for_docker() is True
        mock_sleep.assert_not_called()


def test_wait_for_docker_returns_true_after_retry():
    """初回失敗 → 数回 retry 後に成功"""
    import start_stream_wrapper as wrapper

    with patch("start_stream_wrapper.subprocess.check_call") as mock_call, \
         patch("start_stream_wrapper.time.sleep") as mock_sleep:
        mock_call.side_effect = [
            subprocess.CalledProcessError(1, "docker"),
            subprocess.CalledProcessError(1, "docker"),
            0,
        ]

        assert wrapper.wait_for_docker() is True
        assert mock_sleep.call_count == 2


def test_wait_for_docker_timeout_returns_false():
    """60 秒応答なし → False"""
    import start_stream_wrapper as wrapper

    with patch("start_stream_wrapper.subprocess.check_call") as mock_call, \
         patch("start_stream_wrapper.time.sleep") as mock_sleep:
        mock_call.side_effect = subprocess.CalledProcessError(1, "docker")

        assert wrapper.wait_for_docker() is False
        assert mock_sleep.call_count == wrapper.DOCKER_WAIT_RETRIES


def test_main_installs_30_minute_deadline():
    """A3: 7/7 wedge インシデント対策。30分でハングを強制終了する deadline。"""
    import start_stream_wrapper as wrapper

    with patch("start_stream_wrapper.install_deadline") as mock_install, \
         patch("start_stream_wrapper.exclusive_run") as mock_lock, \
         patch("start_stream_wrapper.wait_for_docker", return_value=True), \
         patch("start_stream_wrapper.subprocess.Popen") as mock_popen, \
         patch("start_stream_wrapper.register_child"):
        mock_lock.return_value.__enter__.return_value = None
        mock_lock.return_value.__exit__.return_value = False
        mock_popen.return_value.wait.return_value = 0

        with pytest.raises(SystemExit):
            wrapper.main()

        mock_install.assert_called_once_with(30 * 60, "start_stream_wrapper")


def test_main_exits_with_compose_returncode_on_success():
    """Docker 起動 → compose run 実行 → returncode を伝搬"""
    import start_stream_wrapper as wrapper

    with patch("start_stream_wrapper.exclusive_run") as mock_lock, \
         patch("start_stream_wrapper.wait_for_docker", return_value=True), \
         patch("start_stream_wrapper.subprocess.Popen") as mock_popen, \
         patch("start_stream_wrapper.register_child") as mock_register:
        mock_lock.return_value.__enter__.return_value = None
        mock_lock.return_value.__exit__.return_value = False
        mock_popen.return_value.wait.return_value = 0

        with pytest.raises(SystemExit) as exc_info:
            wrapper.main()

        assert exc_info.value.code == 0
        compose_args = mock_popen.call_args[0][0]
        assert "compose" in compose_args
        assert "start_stream.py" in compose_args[-1]
        assert mock_popen.call_args[1].get("start_new_session") is True
        mock_register.assert_called_once_with(mock_popen.return_value)


def test_main_exits_with_1_and_alerts_on_docker_timeout():
    """Docker daemon 起動失敗 → exit 1 + アラートメール"""
    import start_stream_wrapper as wrapper

    with patch("start_stream_wrapper.exclusive_run") as mock_lock, \
         patch("start_stream_wrapper.wait_for_docker", return_value=False), \
         patch("start_stream_wrapper.subprocess.Popen") as mock_popen, \
         patch("start_stream_wrapper.send_alert_email") as mock_alert:
        mock_lock.return_value.__enter__.return_value = None
        mock_lock.return_value.__exit__.return_value = False

        with pytest.raises(SystemExit) as exc_info:
            wrapper.main()

        assert exc_info.value.code == 1
        mock_popen.assert_not_called()
        mock_alert.assert_called_once()


def test_main_skips_when_already_running():
    """orchestrator と既存 start.plist が同時発火しても 2 つ目は lock で skip (5/21 OBS クラッシュ回帰)"""
    from rct.lockfile import AlreadyRunning

    import start_stream_wrapper as wrapper

    with patch("start_stream_wrapper.exclusive_run") as mock_lock, \
         patch("start_stream_wrapper.wait_for_docker") as mock_wait, \
         patch("start_stream_wrapper.subprocess.Popen") as mock_popen:
        mock_lock.return_value.__enter__.side_effect = AlreadyRunning("locked")
        mock_lock.return_value.__exit__.return_value = False

        with pytest.raises(SystemExit) as exc_info:
            wrapper.main()

        assert exc_info.value.code == 0
        mock_wait.assert_not_called()
        mock_popen.assert_not_called()


def test_main_acquires_lock_before_compose_run():
    """正常系: lock 取得 → wait_for_docker → compose run"""
    import start_stream_wrapper as wrapper

    with patch("start_stream_wrapper.exclusive_run") as mock_lock, \
         patch("start_stream_wrapper.wait_for_docker", return_value=True), \
         patch("start_stream_wrapper.subprocess.Popen") as mock_popen, \
         patch("start_stream_wrapper.register_child"):
        mock_lock.return_value.__enter__.return_value = None
        mock_lock.return_value.__exit__.return_value = False
        mock_popen.return_value.wait.return_value = 0

        with pytest.raises(SystemExit) as exc_info:
            wrapper.main()

        assert exc_info.value.code == 0
        mock_popen.assert_called_once()
