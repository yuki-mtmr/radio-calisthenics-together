"""fix_broadcasts.py の characterization テスト。

タイトル形式「みんなでラジオ体操 (YYYY/MM/DD HH:MM)」と JST→UTC (-9h) 変換は
配信枠の dedup / verify が文字列一致で依存する契約。
"""
from datetime import datetime
from unittest.mock import patch

import fix_broadcasts


def _bc(id_, title):
    return {"id": id_, "snippet": {"title": title}}


def test_updates_broadcast_matching_today():
    """今日の日付を含む枠は正しいタイトルと UTC 開始時刻で update される。"""
    fixed_now = datetime(2026, 6, 10, 12, 0, 0)
    with patch("fix_broadcasts.YouTubeClient") as mock_yt_cls, \
         patch("fix_broadcasts.settings") as mock_settings, \
         patch("fix_broadcasts.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_settings.STREAM_START_TIME = "06:59"

        yt = mock_yt_cls.return_value
        yt.list_upcoming_broadcasts.return_value = [
            _bc("b1", "みんなでラジオ体操 (2026/06/10 06:59)")
        ]

        fix_broadcasts.fix_upcoming_broadcasts()

        update = yt.youtube.liveBroadcasts.return_value.update
        assert update.call_count == 1
        _, kwargs = update.call_args
        body = kwargs["body"]
        assert body["id"] == "b1"
        assert body["snippet"]["title"] == "みんなでラジオ体操 (2026/06/10 06:59)"
        # JST 06:59 は UTC では前日 21:59
        assert body["snippet"]["scheduledStartTime"] == "2026-06-09T21:59:00Z"


def test_no_upcoming_broadcasts_no_update():
    """upcoming が空なら update を呼ばず終了する。"""
    with patch("fix_broadcasts.YouTubeClient") as mock_yt_cls, \
         patch("fix_broadcasts.settings") as mock_settings:
        mock_settings.STREAM_START_TIME = "06:59"
        yt = mock_yt_cls.return_value
        yt.list_upcoming_broadcasts.return_value = []

        fix_broadcasts.fix_upcoming_broadcasts()

        yt.youtube.liveBroadcasts.return_value.update.assert_not_called()


def test_update_failure_is_swallowed():
    """個別 update の失敗は握り潰してループ継続する (例外を上げない)。"""
    fixed_now = datetime(2026, 6, 10, 12, 0, 0)
    with patch("fix_broadcasts.YouTubeClient") as mock_yt_cls, \
         patch("fix_broadcasts.settings") as mock_settings, \
         patch("fix_broadcasts.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_settings.STREAM_START_TIME = "06:59"

        yt = mock_yt_cls.return_value
        yt.list_upcoming_broadcasts.return_value = [
            _bc("b1", "みんなでラジオ体操 (2026/06/10 06:59)")
        ]
        yt.youtube.liveBroadcasts.return_value.update.return_value.execute.side_effect = (
            Exception("API down")
        )

        # 例外が伝播しないことが契約
        fix_broadcasts.fix_upcoming_broadcasts()
