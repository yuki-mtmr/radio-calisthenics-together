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
        with patch('rct.obs_client.time.sleep'):  # speed up test
            mock_obs_client.start_streaming()

        # Check if media restart was triggered
        mock_obs_client.client.trigger_media_input_action.assert_called_with(
            'test_video.mp4',
            "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART"
        )
        # Check if streaming started
        mock_obs_client.client.start_stream.assert_called()


def test_start_streaming_waits_for_media_buffer_after_restart(mock_obs_client):
    """media restart 後に MEDIA_BUFFER_WAIT_SEC 秒待つ。

    4/30インシデント: 0.012秒で start_stream を呼んだ結果バッファ未蓄積で
    実効0.5fps、YouTubeに stalled stream と判断され15分で切断された。
    """
    from rct.obs_client import MEDIA_BUFFER_WAIT_SEC

    with patch.object(settings, 'OBS_MEDIA_SOURCE_NAME', 'test_video.mp4'):
        with patch('rct.obs_client.time.sleep') as mock_sleep:
            mock_obs_client.start_streaming()

        sleep_durations = [c.args[0] for c in mock_sleep.call_args_list]
        assert MEDIA_BUFFER_WAIT_SEC in sleep_durations

def test_start_streaming_force_resets_when_already_active(mock_obs_client):
    """OBSが既に streaming 中（壊れた状態の可能性）の場合、強制 stop → start で復旧する。

    4/25からのインシデント: OBSが output_active=True のまま reconnect ループに陥り、
    旧実装は「already active」で start を呼ばなかった結果、新broadcastに送出されなかった。
    """
    mock_obs_client.client.get_stream_status.return_value.output_active = True
    mock_obs_client.start_streaming()
    mock_obs_client.client.stop_stream.assert_called()
    mock_obs_client.client.start_stream.assert_called()
    method_names = [c[0] for c in mock_obs_client.client.method_calls]
    assert method_names.index("stop_stream") < method_names.index("start_stream")


def test_start_streaming_when_inactive_does_not_force_stop(mock_obs_client):
    mock_obs_client.client.get_stream_status.return_value.output_active = False
    mock_obs_client.start_streaming()
    mock_obs_client.client.stop_stream.assert_not_called()
    mock_obs_client.client.start_stream.assert_called()


def test_stop_streaming_when_already_stopped_returns_true(mock_obs_client):
    """OBSが既に停止状態（output_active=False）なら stop は no-op で True を返す。"""
    mock_obs_client.client.get_stream_status.return_value.output_active = False
    result = mock_obs_client.stop_streaming()
    assert result is True
    mock_obs_client.client.stop_stream.assert_not_called()


def test_stop_streaming_treats_501_as_success(mock_obs_client):
    """OBSがStopStreamで501（既に止まってる）を返すケースを正常終了として扱う。"""
    from obsws_python.error import OBSSDKRequestError

    mock_obs_client.client.get_stream_status.return_value.output_active = True
    mock_obs_client.client.stop_stream.side_effect = OBSSDKRequestError(
        "StopStream", 501, "Output not active"
    )
    result = mock_obs_client.stop_streaming()
    assert result is True
