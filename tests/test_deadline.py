"""rct.deadline の仕様テスト (TDD: 実装より先に作成)。

7/7 インシデント対策の最終防衛線。各エントリポイントの「全体実行時間上限」を
signal.alarm で強制する。ハンドラは deadline 超過時にログ・アラート・
os._exit(1) を行う。

テスト方針: signal を実際には使わず、ハンドラ生成関数を直接呼んで検証する
(実 SIGALRM を使う短時間テストは 1 本だけ許容)。
"""
import signal
import time
from unittest.mock import MagicMock, patch

from rct import deadline


def test_make_handler_calls_os_exit_1():
    with patch("rct.deadline.os._exit") as mock_exit, \
         patch("rct.deadline.send_alert_email"), \
         patch("rct.deadline.logger"):
        handler = deadline._make_handler(seconds=600, name="health_monitor", on_timeout=None)
        handler(signal.SIGALRM, None)

        mock_exit.assert_called_once_with(1)


def test_make_handler_logs_error_with_name_and_seconds():
    with patch("rct.deadline.os._exit"), \
         patch("rct.deadline.send_alert_email"), \
         patch("rct.deadline.logger") as mock_logger:
        handler = deadline._make_handler(seconds=600, name="health_monitor", on_timeout=None)
        handler(signal.SIGALRM, None)

        mock_logger.error.assert_called_once()
        message = mock_logger.error.call_args[0][0]
        assert "health_monitor" in message
        assert "600" in message


def test_make_handler_sends_alert_email():
    with patch("rct.deadline.os._exit"), \
         patch("rct.deadline.send_alert_email") as mock_alert, \
         patch("rct.deadline.logger"):
        handler = deadline._make_handler(seconds=1200, name="prepare_environment", on_timeout=None)
        handler(signal.SIGALRM, None)

        mock_alert.assert_called_once()
        subject = mock_alert.call_args[0][0]
        assert "prepare_environment" in subject


def test_make_handler_calls_on_timeout_before_exit():
    with patch("rct.deadline.os._exit") as mock_exit, \
         patch("rct.deadline.send_alert_email"), \
         patch("rct.deadline.logger"):
        on_timeout = MagicMock()
        handler = deadline._make_handler(seconds=900, name="stop_stream_wrapper", on_timeout=on_timeout)
        handler(signal.SIGALRM, None)

        on_timeout.assert_called_once()
        mock_exit.assert_called_once_with(1)


def test_make_handler_swallows_on_timeout_exception():
    """on_timeout が例外を投げても os._exit(1) は必ず実行される (最終防衛線)。"""
    with patch("rct.deadline.os._exit") as mock_exit, \
         patch("rct.deadline.send_alert_email"), \
         patch("rct.deadline.logger"):
        on_timeout = MagicMock(side_effect=RuntimeError("boom"))
        handler = deadline._make_handler(seconds=900, name="orchestrator", on_timeout=on_timeout)
        handler(signal.SIGALRM, None)

        mock_exit.assert_called_once_with(1)


def test_make_handler_swallows_alert_email_exception():
    """アラートメール送信が失敗しても os._exit(1) は必ず実行される。"""
    with patch("rct.deadline.os._exit") as mock_exit, \
         patch("rct.deadline.send_alert_email", side_effect=RuntimeError("smtp down")), \
         patch("rct.deadline.logger"):
        handler = deadline._make_handler(seconds=900, name="orchestrator", on_timeout=None)
        handler(signal.SIGALRM, None)

        mock_exit.assert_called_once_with(1)


def test_install_deadline_registers_sigalrm_and_schedules_alarm():
    with patch("rct.deadline.signal.signal") as mock_signal, \
         patch("rct.deadline.signal.alarm") as mock_alarm:
        deadline.install_deadline(seconds=4500, name="orchestrator")

        mock_signal.assert_called_once()
        assert mock_signal.call_args[0][0] == signal.SIGALRM
        mock_alarm.assert_called_once_with(4500)


def test_register_child_is_killed_via_killpg_on_deadline():
    """HIGH: deadline 発火時に登録済み子プロセスを os.killpg で確実に殺す。

    subprocess.run/Popen (docker compose run 等) は deadline (SIGALRM) だけでは
    殺せない。register_child で登録した子は start_new_session=True 前提で
    自身の pgid を持つため、killpg でプロセスグループごと殺す。
    """
    with patch("rct.deadline.os._exit"), \
         patch("rct.deadline.send_alert_email"), \
         patch("rct.deadline.logger"), \
         patch("rct.deadline.os.getpgid", return_value=555) as mock_getpgid, \
         patch("rct.deadline.os.killpg") as mock_killpg:
        deadline._registered_children.clear()
        proc = MagicMock(pid=123)
        deadline.register_child(proc)

        handler = deadline._make_handler(seconds=60, name="orchestrator", on_timeout=None)
        handler(signal.SIGALRM, None)

        mock_getpgid.assert_called_once_with(123)
        mock_killpg.assert_called_once_with(555, signal.SIGKILL)


def test_register_child_swallows_killpg_errors():
    """子プロセスが既に終了している (getpgid が失敗する) 場合でも os._exit(1) は必ず実行される。"""
    with patch("rct.deadline.os._exit") as mock_exit, \
         patch("rct.deadline.send_alert_email"), \
         patch("rct.deadline.logger"), \
         patch("rct.deadline.os.getpgid", side_effect=ProcessLookupError()), \
         patch("rct.deadline.os.killpg") as mock_killpg:
        deadline._registered_children.clear()
        proc = MagicMock(pid=999)
        deadline.register_child(proc)

        handler = deadline._make_handler(seconds=60, name="orchestrator", on_timeout=None)
        handler(signal.SIGALRM, None)

        mock_killpg.assert_not_called()
        mock_exit.assert_called_once_with(1)


def test_register_child_kills_multiple_children():
    with patch("rct.deadline.os._exit"), \
         patch("rct.deadline.send_alert_email"), \
         patch("rct.deadline.logger"), \
         patch("rct.deadline.os.getpgid", side_effect=lambda pid: pid * 10) as mock_getpgid, \
         patch("rct.deadline.os.killpg") as mock_killpg:
        deadline._registered_children.clear()
        deadline.register_child(MagicMock(pid=1))
        deadline.register_child(MagicMock(pid=2))

        handler = deadline._make_handler(seconds=60, name="orchestrator", on_timeout=None)
        handler(signal.SIGALRM, None)

        assert mock_killpg.call_count == 2


def test_install_deadline_clears_previously_registered_children():
    """install_deadline 呼び出し (= 新しいエントリポイントの開始) で登録をリセットする。"""
    deadline._registered_children.clear()
    deadline.register_child(MagicMock(pid=1))

    with patch("rct.deadline.signal.signal"), patch("rct.deadline.signal.alarm"):
        deadline.install_deadline(seconds=10, name="x")

    assert deadline._registered_children == []


def test_install_deadline_real_sigalrm_fires_handler():
    """短時間の実 SIGALRM で、実際に signal 経由でハンドラが起動することを確認する。"""
    triggered = []

    def fake_handler(signum, frame):
        triggered.append(True)

    with patch("rct.deadline._make_handler", return_value=fake_handler):
        try:
            deadline.install_deadline(seconds=1, name="test_task")
            time.sleep(1.5)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, signal.SIG_DFL)

    assert triggered == [True]
