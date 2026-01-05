import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from rct.youtube_client import YouTubeClient
from rct.settings import settings

@pytest.fixture
def mock_youtube_client():
    with patch('rct.youtube_client.build') as mock_build:
        # Mocking open(token.pickle) and os.path.exists
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', MagicMock()):
                with patch('pickle.load', return_value=MagicMock()):
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
