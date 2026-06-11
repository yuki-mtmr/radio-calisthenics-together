"""P4 SRP 分解の確認テスト。

- youtube_client: _get_service が _load_cached_creds / _refresh_creds_with_retry /
  _run_new_auth_flow / _save_creds に分解されていること
- stop_stream: _tomorrow_start_iso が純関数として抽出されていること
- start_stream: _find_or_create_broadcast / _update_obs_stream_key / _ensure_media_visible が
  抽出されていること
"""
from datetime import datetime
from unittest.mock import MagicMock, mock_open, patch

import pytest


# ---------------------------------------------------------------- youtube_client


def test_youtube_client_has_load_cached_creds():
    """_load_cached_creds が独立したメソッドとして存在する。"""
    from rct.youtube_client import YouTubeClient
    assert hasattr(YouTubeClient, "_load_cached_creds")


def test_youtube_client_has_refresh_creds_with_retry():
    """_refresh_creds_with_retry が独立したメソッドとして存在する。"""
    from rct.youtube_client import YouTubeClient
    assert hasattr(YouTubeClient, "_refresh_creds_with_retry")


def test_youtube_client_has_run_new_auth_flow():
    """_run_new_auth_flow が独立したメソッドとして存在する。"""
    from rct.youtube_client import YouTubeClient
    assert hasattr(YouTubeClient, "_run_new_auth_flow")


def test_youtube_client_has_save_creds():
    """_save_creds が独立したメソッドとして存在する。"""
    from rct.youtube_client import YouTubeClient
    assert hasattr(YouTubeClient, "_save_creds")


def test_load_cached_creds_returns_none_when_file_missing(tmp_path):
    """token ファイルが無ければ None を返す。"""
    from rct.youtube_client import YouTubeClient

    with patch("rct.youtube_client.build"), \
         patch("os.path.exists", return_value=False), \
         patch("rct.youtube_client.time.sleep"):

        creds = MagicMock()
        creds.valid = True
        with patch("pickle.load", return_value=creds):
            client = YouTubeClient.__new__(YouTubeClient)
            client.token_path = str(tmp_path / "nonexistent.pickle")
            result = client._load_cached_creds()

    assert result is None


def test_save_creds_writes_pickle(tmp_path):
    """_save_creds が token_path に pickle.dump する。"""
    from rct.youtube_client import YouTubeClient

    client = YouTubeClient.__new__(YouTubeClient)
    client.token_path = str(tmp_path / "token.pickle")
    # MagicMock は pickle 不可なので picklable な stub を使う
    creds_data = {"access_token": "tok", "valid": True}

    client._save_creds(creds_data)

    import pickle
    with open(client.token_path, "rb") as f:
        loaded = pickle.load(f)
    assert loaded == creds_data


def test_refresh_creds_with_retry_returns_creds_on_success():
    """1 回で成功した場合、更新済み creds を返す。"""
    from rct.youtube_client import YouTubeClient

    client = YouTubeClient.__new__(YouTubeClient)
    creds = MagicMock()
    creds.valid = False
    creds.expired = True
    creds.refresh_token = "tok"

    def refresh_ok(req):
        creds.valid = True

    creds.refresh.side_effect = refresh_ok

    with patch("rct.youtube_client.time.sleep"), \
         patch("rct.youtube_client.send_alert_email") as mock_alert:
        result = client._refresh_creds_with_retry(creds)

    assert result is creds
    mock_alert.assert_not_called()


def test_refresh_creds_with_retry_returns_none_and_alerts_on_exhaustion():
    """全滅時は None を返しアラートを送る (アラート件名は凍結契約)。"""
    from google.auth.exceptions import RefreshError
    from rct.youtube_client import YouTubeClient

    client = YouTubeClient.__new__(YouTubeClient)
    creds = MagicMock()
    creds.valid = False
    creds.expired = True
    creds.refresh_token = "tok"
    creds.refresh.side_effect = RefreshError("expired")

    with patch("rct.youtube_client.time.sleep"), \
         patch("rct.youtube_client.send_alert_email") as mock_alert:
        result = client._refresh_creds_with_retry(creds)

    assert result is None
    mock_alert.assert_called_once()
    assert mock_alert.call_args[0][0] == "Token Refresh Failed"


def test_alert_body_uses_dynamic_path():
    """アラート本文のパスが __file__ から動的に解決されている。

    旧実装は `cd /Users/yukimatsumori/projects/radio-calisthenics-together` を
    ハードコードしていた。新実装は Path(__file__).resolve().parents[2] で解決するため
    worktree 名や環境が変わっても正しいパスを指す。
    """
    from google.auth.exceptions import RefreshError
    from pathlib import Path
    import rct.youtube_client as yc_mod
    from rct.youtube_client import YouTubeClient

    client = YouTubeClient.__new__(YouTubeClient)
    creds = MagicMock()
    creds.valid = False
    creds.expired = True
    creds.refresh_token = "tok"
    creds.refresh.side_effect = RefreshError("expired")

    with patch("rct.youtube_client.time.sleep"), \
         patch("rct.youtube_client.send_alert_email") as mock_alert:
        client._refresh_creds_with_retry(creds)

    body = mock_alert.call_args[0][1]
    assert "authenticate_youtube.py" in body
    # 動的パスが本文に含まれている (旧ハードコードの固定文字列ではなく実際のパス)
    expected_root = str(Path(yc_mod.__file__).resolve().parents[2])
    assert expected_root in body


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
