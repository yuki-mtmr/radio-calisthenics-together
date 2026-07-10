"""P4 SRP 分解の確認テスト。

- youtube_client の SRP テストは youtube-autopost ライブラリへの移行に伴い削除
  (2026-07-10)。同等カバレッジはライブラリ側 tests/test_client.py,
  tests/test_auth_retry.py に存在する。rct 側の配線は tests/test_youtube_factory.py
  で検証する。
- stop_stream: _tomorrow_start_iso が純関数として抽出されていること
- start_stream: _find_or_create_broadcast / _update_obs_stream_key / _ensure_media_visible が
  抽出されていること
"""
from datetime import datetime
from unittest.mock import MagicMock, mock_open, patch

import pytest


# ---------------------------------------------------------------- stop_stream


def test_tomorrow_start_iso_exists():
    """_tomorrow_start_iso が抽出された純関数として存在する。"""
    import scripts.stop_stream as ss
    assert hasattr(ss, "_tomorrow_start_iso")


def test_tomorrow_start_iso_jst_to_utc():
    """JST 06:59 の翌日 → UTC 前日 21:59 の ISO 文字列。"""
    from scripts.stop_stream import _tomorrow_start_iso

    now = datetime(2026, 6, 10, 12, 0, 0)
    tomorrow = datetime(2026, 6, 11, 12, 0, 0)
    result = _tomorrow_start_iso(tomorrow, "06:59")
    assert result == "2026-06-10T21:59:00Z"


def test_tomorrow_start_iso_midnight_edge():
    """00:00 は UTC で前日 15:00 になる。"""
    from scripts.stop_stream import _tomorrow_start_iso

    tomorrow = datetime(2026, 6, 11, 0, 0, 0)
    result = _tomorrow_start_iso(tomorrow, "00:00")
    assert result == "2026-06-10T15:00:00Z"


# ---------------------------------------------------------------- start_stream


def test_find_or_create_broadcast_exists():
    """_find_or_create_broadcast が抽出された関数として存在する。"""
    import scripts.start_stream as ss
    assert hasattr(ss, "_find_or_create_broadcast")


def test_find_or_create_broadcast_returns_existing():
    """既存の upcoming 枠が見つかれば create しない。"""
    from scripts.start_stream import _find_or_create_broadcast

    yt = MagicMock()
    yt.list_upcoming_broadcasts.return_value = [
        {"id": "existing", "snippet": {"title": "みんなでラジオ体操 (2026/06/11 06:59)"}}
    ]

    with patch("scripts.start_stream.settings") as ms:
        ms.YOUTUBE_PRIVACY_STATUS = "public"
        result = _find_or_create_broadcast(yt, datetime(2026, 6, 11, 6, 50, 0))

    assert result["id"] == "existing"
    yt.create_broadcast.assert_not_called()


def test_find_or_create_broadcast_creates_when_missing():
    """枠が無ければ create_broadcast を呼ぶ。"""
    from scripts.start_stream import _find_or_create_broadcast

    yt = MagicMock()
    yt.list_upcoming_broadcasts.return_value = []
    yt.create_broadcast.return_value = {"id": "new_id"}

    with patch("scripts.start_stream.settings") as ms:
        ms.YOUTUBE_PRIVACY_STATUS = "public"
        result = _find_or_create_broadcast(yt, datetime(2026, 6, 11, 6, 50, 0))

    yt.create_broadcast.assert_called_once()
    assert result["id"] == "new_id"
