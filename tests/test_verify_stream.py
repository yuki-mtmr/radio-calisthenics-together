"""Tests for verify_stream: 07:01 fallback recovery.

start_stream が失敗した場合に自動で start_stream_wrapper を再実行し、
配信を救済する最終防衛線。
"""
import os
import sys
from unittest.mock import patch

import pytest

project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(project_root, "scripts"))


def test_skips_when_already_broadcasting():
    """配信中なら何もせず exit 0"""
    import verify_stream

    with patch("verify_stream.is_broadcasting", return_value=True), \
         patch("verify_stream.subprocess.run") as mock_run:
        verify_stream.main()
        mock_run.assert_not_called()


def test_triggers_recovery_when_not_broadcasting():
    """配信中でなければ start_stream_wrapper を呼ぶ"""
    import verify_stream

    with patch("verify_stream.is_broadcasting", return_value=False), \
         patch("verify_stream.subprocess.run") as mock_run:
        verify_stream.main()
        mock_run.assert_called_once()
        called_args = mock_run.call_args[0][0]
        assert any("start_stream_wrapper.py" in str(a) for a in called_args)


def test_sends_alert_on_youtube_api_error():
    """is_broadcasting で例外が出たら ALERT メール + exit 1"""
    import verify_stream

    with patch("verify_stream.is_broadcasting", side_effect=RuntimeError("api down")), \
         patch("verify_stream.subprocess.run") as mock_run, \
         patch("verify_stream.send_alert_email") as mock_alert:
        with pytest.raises(SystemExit) as exc_info:
            verify_stream.main()
        assert exc_info.value.code == 1
        mock_run.assert_not_called()
        mock_alert.assert_called_once()


def test_is_broadcasting_true_when_target_title_in_active():
    """active 一覧に「みんなでラジオ体操」を含むタイトルがあれば True"""
    import verify_stream

    with patch("verify_stream.YouTubeClient") as MockYT:
        MockYT.return_value.list_active_broadcasts.return_value = [
            {"snippet": {"title": "みんなでラジオ体操 (2026/05/20 07:00)"}}
        ]
        assert verify_stream.is_broadcasting() is True


def test_is_broadcasting_false_when_empty_active():
    """active 一覧が空なら False"""
    import verify_stream

    with patch("verify_stream.YouTubeClient") as MockYT:
        MockYT.return_value.list_active_broadcasts.return_value = []
        assert verify_stream.is_broadcasting() is False


def test_is_broadcasting_false_when_unrelated_active():
    """別タイトルの active 配信のみなら False (誤検知防止)"""
    import verify_stream

    with patch("verify_stream.YouTubeClient") as MockYT:
        MockYT.return_value.list_active_broadcasts.return_value = [
            {"snippet": {"title": "別の配信"}}
        ]
        assert verify_stream.is_broadcasting() is False
