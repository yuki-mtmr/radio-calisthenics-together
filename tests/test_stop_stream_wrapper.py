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


def test_main_skips_when_already_running():
    """別 trigger が既に動いていれば exit 0 で skip"""
    from rct.lockfile import AlreadyRunning

    import stop_stream_wrapper as wrapper

    with patch("stop_stream_wrapper.exclusive_run") as mock_lock, \
         patch("stop_stream_wrapper.subprocess.run") as mock_run:
        mock_lock.return_value.__enter__.side_effect = AlreadyRunning("locked")
        mock_lock.return_value.__exit__.return_value = False

        with pytest.raises(SystemExit) as exc_info:
            wrapper.main()

        assert exc_info.value.code == 0
        mock_run.assert_not_called()


def test_main_runs_compose_when_lock_available():
    """lock 取れたら docker compose run stop_stream.py を呼ぶ"""
    import stop_stream_wrapper as wrapper

    with patch("stop_stream_wrapper.exclusive_run") as mock_lock, \
         patch("stop_stream_wrapper.subprocess.run") as mock_run:
        mock_lock.return_value.__enter__.return_value = None
        mock_lock.return_value.__exit__.return_value = False
        mock_run.return_value.returncode = 0

        with pytest.raises(SystemExit) as exc_info:
            wrapper.main()

        assert exc_info.value.code == 0
        mock_run.assert_called_once()
        called_args = mock_run.call_args[0][0]
        assert "compose" in called_args
        assert "stop_stream.py" in called_args[-1]


def test_main_propagates_compose_returncode():
    """compose run が non-zero で終わったら同じ code で exit"""
    import stop_stream_wrapper as wrapper

    with patch("stop_stream_wrapper.exclusive_run") as mock_lock, \
         patch("stop_stream_wrapper.subprocess.run") as mock_run:
        mock_lock.return_value.__enter__.return_value = None
        mock_lock.return_value.__exit__.return_value = False
        mock_run.return_value.returncode = 2

        with pytest.raises(SystemExit) as exc_info:
            wrapper.main()

        assert exc_info.value.code == 2
