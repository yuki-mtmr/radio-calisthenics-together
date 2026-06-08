"""Tests for orchestrator: prepare → start → stop の順序保証フロー。

段階 2 の中核。launchd 取りこぼしに 1 回耐えれば全フロー成立する設計を担保する。
"""
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch, call

import pytest

project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(project_root, "scripts"))


def test_main_skips_when_already_running():
    """別 trigger が既に動いていれば exit 0 で skip"""
    from rct.lockfile import AlreadyRunning

    import orchestrator

    with patch("orchestrator.exclusive_run") as mock_lock, \
         patch("orchestrator._run_full_flow") as mock_flow:
        mock_lock.return_value.__enter__.side_effect = AlreadyRunning("locked")
        mock_lock.return_value.__exit__.return_value = False

        with pytest.raises(SystemExit) as exc_info:
            orchestrator.main()

        assert exc_info.value.code == 0
        mock_flow.assert_not_called()


def test_main_runs_full_flow_with_caffeinate():
    """lock 取得 → caffeinate Popen → full_flow → caffeinate terminate"""
    import orchestrator

    fake_caffeinate = MagicMock()
    with patch("orchestrator.exclusive_run") as mock_lock, \
         patch("orchestrator.subprocess.Popen", return_value=fake_caffeinate) as mock_popen, \
         patch("orchestrator._run_full_flow") as mock_flow:
        mock_lock.return_value.__enter__.return_value = None
        mock_lock.return_value.__exit__.return_value = False

        orchestrator.main()

        # caffeinate が起動された
        mock_popen.assert_called_once()
        popen_args = mock_popen.call_args[0][0]
        assert popen_args[0] == "/usr/bin/caffeinate"
        assert "-dis" in popen_args

        # full_flow が実行された
        mock_flow.assert_called_once()

        # caffeinate が terminate された
        fake_caffeinate.terminate.assert_called_once()


def test_caffeinate_terminated_even_on_flow_failure():
    """_run_full_flow が例外を投げても caffeinate は必ず terminate される"""
    import orchestrator

    fake_caffeinate = MagicMock()
    with patch("orchestrator.exclusive_run") as mock_lock, \
         patch("orchestrator.subprocess.Popen", return_value=fake_caffeinate), \
         patch("orchestrator._run_full_flow", side_effect=RuntimeError("boom")), \
         patch("orchestrator.send_alert_email") as mock_alert:
        mock_lock.return_value.__enter__.return_value = None
        mock_lock.return_value.__exit__.return_value = False

        with pytest.raises(SystemExit) as exc_info:
            orchestrator.main()

        assert exc_info.value.code == 1
        fake_caffeinate.terminate.assert_called_once()
        mock_alert.assert_called_once()


def test_full_flow_runs_prepare_then_start_then_stop_in_order():
    """prepare → wait → start → wait → stop の順で呼ばれる"""
    import orchestrator

    call_order = []

    def record_prepare():
        call_order.append("prepare")

    def record_start():
        call_order.append("start")

    def record_stop():
        call_order.append("stop")

    with patch("orchestrator._run_prepare", side_effect=record_prepare), \
         patch("orchestrator._run_start", side_effect=record_start), \
         patch("orchestrator._run_stop", side_effect=record_stop), \
         patch("orchestrator._sleep_until"):
        orchestrator._run_full_flow()

    assert call_order == ["prepare", "start", "stop"]


def test_full_flow_sleeps_until_correct_target_times():
    """sleep target が STREAM_START と STREAM_STOP の今日の時刻と一致する"""
    import orchestrator

    sleep_targets = []

    def record_sleep(target_dt):
        sleep_targets.append((target_dt.hour, target_dt.minute))

    with patch("orchestrator._run_prepare"), \
         patch("orchestrator._run_start"), \
         patch("orchestrator._run_stop"), \
         patch("orchestrator._sleep_until", side_effect=record_sleep):
        orchestrator._run_full_flow()

    assert sleep_targets == [
        (orchestrator.STREAM_START_HOUR, orchestrator.STREAM_START_MINUTE),
        (orchestrator.STREAM_STOP_HOUR, orchestrator.STREAM_STOP_MINUTE),
    ]


def test_sleep_until_returns_immediately_when_target_is_past():
    """target_dt が既に過ぎていれば time.sleep を呼ばない"""
    import orchestrator

    past = datetime.now().replace(year=2000)
    with patch("orchestrator.time.sleep") as mock_sleep:
        orchestrator._sleep_until(past)
        mock_sleep.assert_not_called()


def test_sleep_until_sleeps_for_positive_delta():
    """target_dt が未来なら time.sleep に正の秒数を渡す"""
    import orchestrator

    future = datetime.now().replace(year=2099)
    with patch("orchestrator.time.sleep") as mock_sleep:
        orchestrator._sleep_until(future)
        mock_sleep.assert_called_once()
        assert mock_sleep.call_args[0][0] > 0


def test_run_prepare_invokes_python_with_correct_script():
    import orchestrator

    with patch("orchestrator.subprocess.run") as mock_run:
        orchestrator._run_prepare()
        called = mock_run.call_args[0][0]
        assert "prepare_environment.py" in called[-1]


def test_run_start_invokes_python_with_wrapper():
    import orchestrator

    with patch("orchestrator.subprocess.run") as mock_run:
        orchestrator._run_start()
        called = mock_run.call_args[0][0]
        assert "start_stream_wrapper.py" in called[-1]


def test_run_stop_invokes_stop_wrapper():
    """orchestrator は stop_stream_wrapper.py 経由で stop を呼ぶ (lock 統合)"""
    import orchestrator

    with patch("orchestrator.subprocess.run") as mock_run:
        orchestrator._run_stop()
        called = mock_run.call_args[0][0]
        assert "stop_stream_wrapper.py" in called[-1]
