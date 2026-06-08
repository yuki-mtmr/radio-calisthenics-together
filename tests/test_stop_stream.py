"""stop_stream.py の回帰テスト。

2026-05-17 インシデント: OBS 接続失敗時に sys.exit(0) で早期終了し、
翌日の YouTube 配信枠が作成されないバグ。OBS 停止失敗と
翌日予約は独立して実行される必要がある。
"""
import sys
from unittest.mock import MagicMock, patch

import pytest


def test_schedule_tomorrow_runs_even_when_obs_disconnected():
    """OBS 接続失敗時も翌日の YouTube 予約が実行される (2026-05-17 回帰)。"""
    with patch("scripts.stop_stream.OBSClient") as mock_obs_class, \
         patch("scripts.stop_stream.YouTubeClient") as mock_yt_class, \
         patch("scripts.stop_stream.settings") as mock_settings:

        mock_obs = MagicMock()
        mock_obs.connect.return_value = False
        mock_obs_class.return_value = mock_obs

        mock_yt = MagicMock()
        mock_yt.find_broadcast_by_date.return_value = None
        mock_yt_class.return_value = mock_yt

        mock_settings.STREAM_START_TIME = "07:00"
        mock_settings.YOUTUBE_PRIVACY_STATUS = "public"

        from scripts.stop_stream import main

        main()

        mock_yt.create_broadcast.assert_called_once()
        _, kwargs = mock_yt.create_broadcast.call_args
        assert "start_time_iso" in kwargs


def test_schedule_skipped_when_tomorrow_already_exists():
    """翌日の枠が既にあれば create_broadcast を呼ばない。"""
    with patch("scripts.stop_stream.OBSClient") as mock_obs_class, \
         patch("scripts.stop_stream.YouTubeClient") as mock_yt_class, \
         patch("scripts.stop_stream.settings") as mock_settings:

        mock_obs = MagicMock()
        mock_obs.connect.return_value = True
        mock_obs.stop_streaming.return_value = True
        mock_obs_class.return_value = mock_obs

        mock_yt = MagicMock()
        mock_yt.find_broadcast_by_date.return_value = {"id": "existing_id", "snippet": {"title": "existing"}}
        mock_yt_class.return_value = mock_yt

        mock_settings.STREAM_START_TIME = "07:00"
        mock_settings.YOUTUBE_PRIVACY_STATUS = "public"

        from scripts.stop_stream import main

        main()

        mock_yt.create_broadcast.assert_not_called()


def test_obs_stop_success_still_schedules_tomorrow():
    """OBS 停止成功時も従来通り翌日予約まで行う。"""
    with patch("scripts.stop_stream.OBSClient") as mock_obs_class, \
         patch("scripts.stop_stream.YouTubeClient") as mock_yt_class, \
         patch("scripts.stop_stream.settings") as mock_settings:

        mock_obs = MagicMock()
        mock_obs.connect.return_value = True
        mock_obs.stop_streaming.return_value = True
        mock_obs_class.return_value = mock_obs

        mock_yt = MagicMock()
        mock_yt.find_broadcast_by_date.return_value = None
        mock_yt_class.return_value = mock_yt

        mock_settings.STREAM_START_TIME = "07:00"
        mock_settings.YOUTUBE_PRIVACY_STATUS = "public"

        from scripts.stop_stream import main

        main()

        mock_obs.stop_streaming.assert_called_once()
        mock_yt.create_broadcast.assert_called_once()


def test_youtube_failure_exits_with_error():
    """YouTube 予約失敗時は exit code 1。"""
    with patch("scripts.stop_stream.OBSClient") as mock_obs_class, \
         patch("scripts.stop_stream.YouTubeClient") as mock_yt_class, \
         patch("scripts.stop_stream.settings") as mock_settings:

        mock_obs = MagicMock()
        mock_obs.connect.return_value = True
        mock_obs.stop_streaming.return_value = True
        mock_obs_class.return_value = mock_obs

        mock_yt_class.side_effect = Exception("YouTube API down")

        mock_settings.STREAM_START_TIME = "07:00"
        mock_settings.YOUTUBE_PRIVACY_STATUS = "public"

        from scripts.stop_stream import main

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
