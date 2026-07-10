"""rct.youtube.make_youtube_client の配線テスト。

YouTubeClient 本体の挙動 (認証/リトライ/API呼び出し) は youtube-autopost
ライブラリ側 (vendor 元リポジトリ) でテスト済みのため、ここでは
factory が正しいパス・アラートコールバックを配線しているかのみ検証する。
"""
from unittest.mock import patch

from rct.youtube import make_youtube_client


def test_make_youtube_client_wires_send_alert_email_as_on_alert():
    with patch("rct.youtube.YouTubeClient") as mock_cls:
        make_youtube_client()
        _, kwargs = mock_cls.call_args
        assert callable(kwargs["on_alert"])


def test_make_youtube_client_on_alert_calls_send_alert_email():
    with patch("rct.youtube.YouTubeClient") as mock_cls, \
         patch("rct.youtube.send_alert_email") as mock_send:
        make_youtube_client()
        on_alert = mock_cls.call_args.kwargs["on_alert"]
        on_alert("subj", "body")
        mock_send.assert_called_once_with("subj", "body")


def test_make_youtube_client_uses_default_paths():
    with patch("rct.youtube.YouTubeClient") as mock_cls:
        make_youtube_client()
        _, kwargs = mock_cls.call_args
        assert kwargs["credentials_path"] == "config/youtube/client_secrets.json"
        assert kwargs["token_path"] == "config/youtube/token.json"


def test_make_youtube_client_accepts_path_overrides():
    with patch("rct.youtube.YouTubeClient") as mock_cls:
        make_youtube_client(credentials_path="c.json", token_path="t.json")
        _, kwargs = mock_cls.call_args
        assert kwargs["credentials_path"] == "c.json"
        assert kwargs["token_path"] == "t.json"


def test_make_youtube_client_returns_client_instance():
    with patch("rct.youtube.YouTubeClient") as mock_cls:
        result = make_youtube_client()
        assert result is mock_cls.return_value
