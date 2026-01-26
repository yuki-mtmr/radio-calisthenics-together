import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, mock_open
from google.auth.exceptions import RefreshError
from rct.youtube_client import YouTubeClient
from rct.settings import settings

@pytest.fixture
def mock_youtube_client():
    with patch('rct.youtube_client.build') as mock_build:
        # Mocking open(token.pickle) and os.path.exists
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', MagicMock()):
                # 有効期限を30日後に設定
                mock_creds = MagicMock()
                mock_creds.expiry = datetime.utcnow() + timedelta(days=30)
                with patch('pickle.load', return_value=mock_creds):
                    client = YouTubeClient()
                    yield client

def test_find_broadcast_by_date(mock_youtube_client):
    # Setup mock return for liveBroadcasts().list().execute()
    mock_item = {
        'id': 'test_id',
        'snippet': {'title': 'みんなでラジオ体操 (2026/01/07 07:00)'}
    }
    mock_youtube_client.youtube.liveBroadcasts().list().execute.return_value = {
        'items': [mock_item]
    }

    # Match
    result = mock_youtube_client.find_broadcast_by_date('2026/01/07')
    assert result['id'] == 'test_id'

    # No match
    result = mock_youtube_client.find_broadcast_by_date('2026/01/08')
    assert result is None

def test_create_broadcast_args(mock_youtube_client):
    mock_youtube_client.create_broadcast(
        title="Test Title",
        description="Test Desc",
        start_time_iso="2026-01-07T22:00:00Z"
    )

    # Check if insert was called with correct body
    args, kwargs = mock_youtube_client.youtube.liveBroadcasts().insert.call_args
    body = kwargs['body']
    assert body['snippet']['title'] == "Test Title"
    assert body['snippet']['scheduledStartTime'] == "2026-01-07T22:00:00Z"
    assert body['status']['privacyStatus'] == "public"
    assert body['contentDetails']['enableAutoStart'] is True


def test_token_refresh_failure_triggers_new_auth():
    """トークンリフレッシュ失敗時に新規認証フローへフォールバックすることを確認"""
    # 期限切れのモッククレデンシャルを作成
    expired_creds = MagicMock()
    expired_creds.valid = False
    expired_creds.expired = True
    expired_creds.refresh_token = 'some_refresh_token'
    # refresh()が呼ばれたときにRefreshErrorを発生させる
    expired_creds.refresh.side_effect = RefreshError("Token has been expired or revoked.")

    # 新規認証用のモッククレデンシャル
    new_creds = MagicMock()
    new_creds.valid = True
    new_creds.expiry = datetime.utcnow() + timedelta(days=30)

    with patch('rct.youtube_client.build') as mock_build, \
         patch('os.path.exists') as mock_exists, \
         patch('builtins.open', mock_open()), \
         patch('pickle.load', return_value=expired_creds), \
         patch('pickle.dump') as mock_dump, \
         patch('rct.youtube_client.InstalledAppFlow') as mock_flow, \
         patch('rct.youtube_client.send_alert_email'):

        # client_secrets.jsonは存在する
        mock_exists.side_effect = lambda path: True

        # 新規認証フローが新しいcredsを返す
        mock_flow.from_client_secrets_file.return_value.run_local_server.return_value = new_creds

        # YouTubeClientを初期化（エラーなく完了することを確認）
        client = YouTubeClient()

        # 新規認証フローが呼ばれたことを確認
        mock_flow.from_client_secrets_file.assert_called_once()
        mock_flow.from_client_secrets_file.return_value.run_local_server.assert_called_once()

        # 新しいcredsが保存されたことを確認
        mock_dump.assert_called()


def test_token_refresh_success_no_email():
    """トークンリフレッシュ成功時は警告メールが送信されないことを確認"""
    # 期限切れだがリフレッシュ可能なモッククレデンシャル
    expired_creds = MagicMock()
    expired_creds.valid = False
    expired_creds.expired = True
    expired_creds.refresh_token = 'some_refresh_token'
    # refresh()成功後のcredsをシミュレート
    def refresh_side_effect(request):
        expired_creds.valid = True
        expired_creds.expiry = datetime.utcnow() + timedelta(hours=1)
    expired_creds.refresh.side_effect = refresh_side_effect

    with patch('rct.youtube_client.build') as mock_build, \
         patch('os.path.exists', return_value=True), \
         patch('builtins.open', mock_open()), \
         patch('pickle.load', return_value=expired_creds), \
         patch('pickle.dump'), \
         patch('rct.youtube_client.send_alert_email') as mock_send_email:

        # YouTubeClientを初期化
        client = YouTubeClient()

        # 警告メールは送信されないことを確認
        mock_send_email.assert_not_called()


def test_token_refresh_failure_sends_alert_email():
    """トークンリフレッシュ失敗時に警告メールが送信されることを確認"""
    # 期限切れでリフレッシュ失敗するモッククレデンシャル
    expired_creds = MagicMock()
    expired_creds.valid = False
    expired_creds.expired = True
    expired_creds.refresh_token = 'some_refresh_token'
    expired_creds.refresh.side_effect = RefreshError("Token has been expired or revoked.")

    # 新規認証用のモッククレデンシャル
    new_creds = MagicMock()
    new_creds.valid = True
    new_creds.expiry = datetime.utcnow() + timedelta(days=30)

    with patch('rct.youtube_client.build') as mock_build, \
         patch('os.path.exists', return_value=True), \
         patch('builtins.open', mock_open()), \
         patch('pickle.load', return_value=expired_creds), \
         patch('pickle.dump'), \
         patch('rct.youtube_client.InstalledAppFlow') as mock_flow, \
         patch('rct.youtube_client.send_alert_email') as mock_send_email:

        # 新規認証フローが新しいcredsを返す
        mock_flow.from_client_secrets_file.return_value.run_local_server.return_value = new_creds

        # YouTubeClientを初期化
        client = YouTubeClient()

        # 警告メールが送信されたことを確認
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args
        assert "Token Refresh Failed" in call_args[0][0]
        assert "再認証" in call_args[0][1]
