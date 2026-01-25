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
