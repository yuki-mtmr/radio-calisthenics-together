"""
notify.py のテスト

send_alert_email 関数のテストを行う。
SMTPをモックしてメール送信をテスト。
"""
import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# srcディレクトリをパスに追加
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(project_root, 'src'))


class TestSendAlertEmail:
    """send_alert_email のテストクラス"""

    def test_send_alert_email_success(self):
        """正常にメール送信できることをテスト"""
        with patch('rct.notify.smtplib.SMTP') as mock_smtp, \
             patch('rct.notify.settings') as mock_settings, \
             patch('rct.notify.logger'):

            mock_settings.ALERT_EMAIL_SENDER = "sender@example.com"
            mock_settings.ALERT_EMAIL_PASSWORD = "password123"
            mock_settings.ALERT_EMAIL_RECEIVER = "receiver@example.com"

            mock_server = MagicMock()
            mock_smtp.return_value = mock_server

            from rct.notify import send_alert_email

            send_alert_email("Test Subject", "Test Body")

            mock_smtp.assert_called_once_with('smtp.gmail.com', 587)
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("sender@example.com", "password123")
            mock_server.sendmail.assert_called_once()
            mock_server.quit.assert_called_once()

    def test_send_alert_email_missing_sender(self):
        """送信者が設定されていない場合、メールを送信しないことをテスト"""
        with patch('rct.notify.smtplib.SMTP') as mock_smtp, \
             patch('rct.notify.settings') as mock_settings, \
             patch('rct.notify.logger') as mock_logger:

            mock_settings.ALERT_EMAIL_SENDER = ""
            mock_settings.ALERT_EMAIL_PASSWORD = "password123"
            mock_settings.ALERT_EMAIL_RECEIVER = "receiver@example.com"

            from rct.notify import send_alert_email

            send_alert_email("Test Subject", "Test Body")

            mock_smtp.assert_not_called()
            mock_logger.warning.assert_called_once()

    def test_send_alert_email_missing_password(self):
        """パスワードが設定されていない場合、メールを送信しないことをテスト"""
        with patch('rct.notify.smtplib.SMTP') as mock_smtp, \
             patch('rct.notify.settings') as mock_settings, \
             patch('rct.notify.logger') as mock_logger:

            mock_settings.ALERT_EMAIL_SENDER = "sender@example.com"
            mock_settings.ALERT_EMAIL_PASSWORD = ""
            mock_settings.ALERT_EMAIL_RECEIVER = "receiver@example.com"

            from rct.notify import send_alert_email

            send_alert_email("Test Subject", "Test Body")

            mock_smtp.assert_not_called()
            mock_logger.warning.assert_called_once()

    def test_send_alert_email_missing_receiver(self):
        """受信者が設定されていない場合、メールを送信しないことをテスト"""
        with patch('rct.notify.smtplib.SMTP') as mock_smtp, \
             patch('rct.notify.settings') as mock_settings, \
             patch('rct.notify.logger') as mock_logger:

            mock_settings.ALERT_EMAIL_SENDER = "sender@example.com"
            mock_settings.ALERT_EMAIL_PASSWORD = "password123"
            mock_settings.ALERT_EMAIL_RECEIVER = ""

            from rct.notify import send_alert_email

            send_alert_email("Test Subject", "Test Body")

            mock_smtp.assert_not_called()
            mock_logger.warning.assert_called_once()

    def test_send_alert_email_smtp_error(self):
        """SMTP接続エラー時にエラーログを出力することをテスト"""
        with patch('rct.notify.smtplib.SMTP') as mock_smtp, \
             patch('rct.notify.settings') as mock_settings, \
             patch('rct.notify.logger') as mock_logger:

            mock_settings.ALERT_EMAIL_SENDER = "sender@example.com"
            mock_settings.ALERT_EMAIL_PASSWORD = "password123"
            mock_settings.ALERT_EMAIL_RECEIVER = "receiver@example.com"

            mock_server = MagicMock()
            mock_server.login.side_effect = Exception("Connection refused")
            mock_smtp.return_value = mock_server

            from rct.notify import send_alert_email

            send_alert_email("Test Subject", "Test Body")

            mock_logger.error.assert_called_once()

    def test_send_alert_email_subject_prefix(self):
        """メール件名に [RCT Alert] プレフィックスが付くことをテスト"""
        with patch('rct.notify.smtplib.SMTP') as mock_smtp, \
             patch('rct.notify.settings') as mock_settings, \
             patch('rct.notify.logger'):

            mock_settings.ALERT_EMAIL_SENDER = "sender@example.com"
            mock_settings.ALERT_EMAIL_PASSWORD = "password123"
            mock_settings.ALERT_EMAIL_RECEIVER = "receiver@example.com"

            mock_server = MagicMock()
            mock_smtp.return_value = mock_server

            from rct.notify import send_alert_email

            send_alert_email("Test Subject", "Test Body")

            # sendmail の第3引数（メール本文）に [RCT Alert] が含まれていることを確認
            call_args = mock_server.sendmail.call_args
            email_content = call_args[0][2]
            assert "[RCT Alert] Test Subject" in email_content
