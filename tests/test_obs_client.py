import pytest
from unittest.mock import MagicMock, patch
from rct.obs_client import OBSClient
from rct.settings import settings

@pytest.fixture
def mock_obs_client():
    with patch('obsws_python.ReqClient'):
        client = OBSClient()
        client.client = MagicMock()
        # Mock connect to just return True
        client.connect = MagicMock(return_value=True)
        # Default mock for get_stream_status
        status = MagicMock()
        status.output_active = False
        client.client.get_stream_status.return_value = status
        yield client

def test_set_scene(mock_obs_client):
    mock_obs_client.set_scene("TEST_SCENE")
    mock_obs_client.client.set_current_program_scene.assert_called_with("TEST_SCENE")

def test_start_streaming_with_media_restart(mock_obs_client):
    # Mock settings
    with patch.object(settings, 'OBS_MEDIA_SOURCE_NAME', 'test_video.mp4'):
        mock_obs_client.start_streaming()

        # Check if media restart was triggered
        mock_obs_client.client.trigger_media_input_action.assert_called_with(
            'test_video.mp4',
            "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART"
        )
        # Check if streaming started
        mock_obs_client.client.start_stream.assert_called()

def test_start_streaming_already_active(mock_obs_client):
    mock_obs_client.client.get_stream_status.return_value.output_active = True
    mock_obs_client.start_streaming()
    mock_obs_client.client.start_stream.assert_not_called()
