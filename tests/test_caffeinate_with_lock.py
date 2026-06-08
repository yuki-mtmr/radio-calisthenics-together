"""Tests for caffeinate_with_lock wrapper."""
import os
import sys
from unittest.mock import patch

import pytest

project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(project_root, "scripts"))


def test_caffeinate_called_when_lock_available():
    """lock 取得成功 → /usr/bin/caffeinate を 22 分起動"""
    import caffeinate_with_lock

    with patch("caffeinate_with_lock.subprocess.run") as mock_run, \
         patch("caffeinate_with_lock.exclusive_run") as mock_lock:
        mock_lock.return_value.__enter__.return_value = None
        mock_lock.return_value.__exit__.return_value = False

        caffeinate_with_lock.main()

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "/usr/bin/caffeinate"
        assert "-dis" in call_args
        assert "1320" in call_args


def test_caffeinate_skipped_when_lock_held():
    """別 trigger が既に caffeinate を保持中 → exit 0 で skip"""
    from rct.lockfile import AlreadyRunning

    import caffeinate_with_lock

    with patch("caffeinate_with_lock.subprocess.run") as mock_run, \
         patch("caffeinate_with_lock.exclusive_run") as mock_lock:
        mock_lock.return_value.__enter__.side_effect = AlreadyRunning("locked")
        mock_lock.return_value.__exit__.return_value = False

        with pytest.raises(SystemExit) as exc_info:
            caffeinate_with_lock.main()

        assert exc_info.value.code == 0
        mock_run.assert_not_called()
