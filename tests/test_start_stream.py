import sys
import pytest
from unittest.mock import MagicMock, patch


def test_email_failure_does_not_crash_script():
    """メール送信が失敗してもスクリプトがsys.exit(1)で終了することを確認"""
    with patch('rct.notify.smtplib.SMTP') as mock_smtp, \
         patch('rct.notify.settings') as mock_notify_settings, \
         patch('scripts.start_stream.YouTubeClient') as mock_yt, \
         patch('scripts.start_stream.OBSClient') as mock_obs, \
         patch('scripts.start_stream.settings') as mock_settings, \
         patch('scripts.start_stream.send_alert_email') as mock_send_email:

        # メール設定あり
        mock_notify_settings.ALERT_EMAIL_SENDER = 'test@example.com'
        mock_notify_settings.ALERT_EMAIL_PASSWORD = 'password'
        mock_notify_settings.ALERT_EMAIL_RECEIVER = 'receiver@example.com'

        # YouTubeClientの初期化で例外を発生させてエラーパスをテスト
        mock_yt.side_effect = Exception("YouTube API Error")

        # メール送信も例外を発生させる
        mock_send_email.side_effect = Exception("SMTP Connection Failed")

        # main関数をインポートして実行
        from scripts.start_stream import main

        # SystemExitが発生することを確認（メール例外で止まらない）
        with pytest.raises(SystemExit) as exc_info:
            main()

        # exit code 1で終了すること
        assert exc_info.value.code == 1

        # send_alert_emailが呼ばれたことを確認
        mock_send_email.assert_called_once()


def test_youtube_init_retries_then_succeeds():
    """YouTubeClient 初期化が瞬断で 1 回目失敗 → 2 回目成功するとき配信を継続 (2026-05-18 回帰)。"""
    call_count = {"n": 0}

    def yt_factory(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise Exception("Unable to find the server at youtube.googleapis.com")
        yt = MagicMock()
        yt.list_upcoming_broadcasts.return_value = []
        yt.create_broadcast.return_value = {"id": "bid"}
        yt.create_stream.return_value = {"id": "sid", "cdn": {"ingestionInfo": {"streamName": "key"}}}
        return yt

    with patch("scripts.start_stream._is_already_broadcasting", return_value=False), \
         patch("scripts.start_stream.YouTubeClient", side_effect=yt_factory), \
         patch("scripts.start_stream.OBSClient") as mock_obs_class, \
         patch("scripts.start_stream.settings") as mock_settings, \
         patch("scripts.start_stream.time.sleep") as mock_sleep:

        mock_settings.STREAM_START_TIME = "07:00"
        mock_settings.YOUTUBE_PRIVACY_STATUS = "public"
        mock_settings.OBS_MEDIA_SOURCE_NAME = "src"
        mock_settings.OBS_SCENE_NAME = "scene"

        mock_obs = MagicMock()
        mock_obs.start_streaming.return_value = True
        mock_obs_class.return_value = mock_obs

        from scripts.start_stream import main
        main()

        assert call_count["n"] == 2
        mock_obs.start_streaming.assert_called_once()


def test_youtube_init_exhausts_retries_then_exits():
    """YouTubeClient が全リトライ失敗時は alert + exit 1 (2026-05-18 回帰)。"""
    with patch("scripts.start_stream._is_already_broadcasting", return_value=False), \
         patch("scripts.start_stream.YouTubeClient") as mock_yt_class, \
         patch("scripts.start_stream.OBSClient") as mock_obs_class, \
         patch("scripts.start_stream.settings") as mock_settings, \
         patch("scripts.start_stream.send_alert_email") as mock_alert, \
         patch("scripts.start_stream.time.sleep") as mock_sleep:

        mock_yt_class.side_effect = Exception("Unable to find the server at youtube.googleapis.com")
        mock_settings.STREAM_START_TIME = "07:00"
        mock_settings.YOUTUBE_PRIVACY_STATUS = "public"

        from scripts.start_stream import main
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        assert mock_yt_class.call_count == 3
        mock_alert.assert_called_once()


def test_start_stream_skips_when_already_broadcasting():
    """orchestrator が先に start を呼んだ後、既存 start.plist が 06:59 に発火しても重複起動しない"""
    with patch("scripts.start_stream._is_already_broadcasting", return_value=True), \
         patch("scripts.start_stream._setup_youtube_broadcast") as mock_setup, \
         patch("scripts.start_stream.OBSClient") as mock_obs:
        from scripts.start_stream import main
        main()
        mock_setup.assert_not_called()
        mock_obs.assert_not_called()


def test_is_already_broadcasting_true_when_target_active():
    """active 一覧に「みんなでラジオ体操」を含むタイトルがあれば True"""
    with patch("scripts.start_stream.YouTubeClient") as MockYT:
        MockYT.return_value.list_active_broadcasts.return_value = [
            {"snippet": {"title": "みんなでラジオ体操 (2026/05/21 07:00)"}}
        ]
        from scripts.start_stream import _is_already_broadcasting
        assert _is_already_broadcasting() is True


def test_is_already_broadcasting_false_when_yt_init_fails():
    """YouTubeClient 初期化失敗時は False (フォールバックして start を試行)"""
    with patch("scripts.start_stream.YouTubeClient", side_effect=Exception("api down")):
        from scripts.start_stream import _is_already_broadcasting
        assert _is_already_broadcasting() is False


def test_email_failure_in_notify_is_logged_and_continues():
    """notify.pyのsend_alert_email内の例外が適切にログされ、例外を投げないことを確認"""
    from rct.notify import send_alert_email

    with patch('rct.notify.smtplib.SMTP') as mock_smtp, \
         patch('rct.notify.settings') as mock_settings, \
         patch('rct.notify.logger') as mock_logger:

        # メール設定あり
        mock_settings.ALERT_EMAIL_SENDER = 'test@example.com'
        mock_settings.ALERT_EMAIL_PASSWORD = 'password'
        mock_settings.ALERT_EMAIL_RECEIVER = 'receiver@example.com'

        # SMTPで例外を発生させる
        mock_smtp.side_effect = Exception("Connection refused")

        # 例外が発生しないことを確認（内部でキャッチされる）
        send_alert_email("Test Subject", "Test Body")

        # エラーがログされたことを確認
        mock_logger.error.assert_called()
