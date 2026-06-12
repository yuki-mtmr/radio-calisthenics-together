import pytest
from unittest.mock import MagicMock, patch
from rct.obs_client import OBSClient
from rct.settings import settings
from tests.conftest import make_settings

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
        # Default mock for get_media_input_status (位置ガードが参照する)
        # 既定では位置0で静止しているものとし、ガードが余計な再送をしないようにする
        media_status = MagicMock()
        media_status.media_cursor = 0
        media_status.media_state = "OBS_MEDIA_STATE_PAUSED"
        client.client.get_media_input_status.return_value = media_status
        yield client

def test_set_scene(mock_obs_client):
    mock_obs_client.set_scene("TEST_SCENE")
    mock_obs_client.client.set_current_program_scene.assert_called_with("TEST_SCENE")

def test_start_streaming_with_media_restart(mock_obs_client):
    # Mock settings
    with patch('rct.obs_client.settings', make_settings(OBS_MEDIA_SOURCE_NAME='test_video.mp4')):
        with patch('rct.obs_client.time.sleep'):  # speed up test
            mock_obs_client.start_streaming()

        # Check if media restart was triggered (among other actions)
        mock_obs_client.client.trigger_media_input_action.assert_any_call(
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

    with patch('rct.obs_client.settings', make_settings(OBS_MEDIA_SOURCE_NAME='test_video.mp4')):
        with patch('rct.obs_client.time.sleep') as mock_sleep:
            mock_obs_client.start_streaming()

        sleep_durations = [c.args[0] for c in mock_sleep.call_args_list]
        assert MEDIA_BUFFER_WAIT_SEC in sleep_durations


def test_start_streaming_pauses_media_during_warmup(mock_obs_client):
    """warmup 中はメディアを PAUSE して動画が進まないようにする。

    5/1インシデント: warmup 5秒の間に動画が再生され、視聴者には
    冒頭5〜10秒が抜けて見えていた。
    """
    with patch('rct.obs_client.settings', make_settings(OBS_MEDIA_SOURCE_NAME='test_video.mp4')):
        with patch('rct.obs_client.time.sleep'):
            mock_obs_client.start_streaming()

        actions = [
            c.args[1] for c in mock_obs_client.client.trigger_media_input_action.call_args_list
        ]
        assert "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART" in actions
        assert "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE" in actions
        assert "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY" in actions
        # 順序: RESTART → PAUSE → ... start_stream ... → PLAY
        assert actions.index("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE") < actions.index(
            "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY"
        )


def test_start_streaming_calls_play_after_start_stream(mock_obs_client):
    """PLAY は start_stream の後に呼ばれる（動画が配信開始後に再生開始される）。"""
    with patch('rct.obs_client.settings', make_settings(OBS_MEDIA_SOURCE_NAME='test_video.mp4')):
        with patch('rct.obs_client.time.sleep'):
            mock_obs_client.start_streaming()

        method_names = [c[0] for c in mock_obs_client.client.method_calls]
        # last trigger_media_input_action (PLAY) should come after start_stream
        play_indices = [
            i for i, c in enumerate(mock_obs_client.client.method_calls)
            if c[0] == "trigger_media_input_action" and c.args[1] == "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY"
        ]
        start_stream_indices = [i for i, n in enumerate(method_names) if n == "start_stream"]
        assert play_indices and start_stream_indices
        assert max(play_indices) > min(start_stream_indices)


def _calls_before(calls, start_idx, action):
    """start_idx より前の trigger_media_input_action(action) のインデックス一覧。"""
    return [
        i for i, c in enumerate(calls)
        if i < start_idx
        and c[0] == "trigger_media_input_action"
        and len(c.args) >= 2 and c.args[1] == action
    ]


def test_media_restart_pause_happen_after_source_enabled(mock_obs_client):
    """RESTART/PAUSE は表示(enable=True)の "後" かつ start_stream の "前" に送る。

    5/1→再発インシデント: enable より前に PAUSE しても、enable 時に OBS の
    restart_on_activate(デフォルトON) が発火して位置0から再生が始まり、PAUSE が
    上書きされる。warmup 中に動画が進んで冒頭5〜10秒が切れていた。enable の後に
    RESTART+PAUSE を送れば、アクティブなソースに対して確実に位置0で凍結できる。
    """
    with patch('rct.obs_client.settings', make_settings(OBS_MEDIA_SOURCE_NAME='test_video.mp4')):
        with patch('rct.obs_client.time.sleep'):
            mock_obs_client.start_streaming()

    calls = mock_obs_client.client.method_calls
    names = [c[0] for c in calls]
    start_idx = names.index("start_stream")

    # 最後の enable(True)（= 表示）のインデックス
    enable_true_idx = max(
        i for i, c in enumerate(calls)
        if c[0] == "set_scene_item_enabled" and len(c.args) >= 3 and c.args[2] is True
    )
    restart_idx = min(_calls_before(calls, start_idx, "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART"))
    pause_idx = min(_calls_before(calls, start_idx, "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE"))

    # enable(True) → RESTART → PAUSE → start_stream の順
    assert enable_true_idx < restart_idx < pause_idx < start_idx


def test_start_streaming_repauses_when_media_drifted(mock_obs_client):
    """位置ガード: warmup 後に media_cursor がドリフトしていたら start_stream 前に再 RESTART+PAUSE。

    restart_on_activate 等で動画が進んでしまったケースを実位置で検知し、配信開始前に
    位置0へ戻す（再発防止の防御層）。
    """
    drift = MagicMock()
    drift.media_cursor = 4500  # 4.5秒進んでしまっている
    drift.media_state = "OBS_MEDIA_STATE_PLAYING"
    mock_obs_client.client.get_media_input_status.return_value = drift

    with patch('rct.obs_client.settings', make_settings(OBS_MEDIA_SOURCE_NAME='test_video.mp4')):
        with patch('rct.obs_client.time.sleep'):
            mock_obs_client.start_streaming()

    calls = mock_obs_client.client.method_calls
    names = [c[0] for c in calls]
    start_idx = names.index("start_stream")

    # 位置を確認したうえで、初回(enable後)＋ガード再送で RESTART/PAUSE が2回以上
    mock_obs_client.client.get_media_input_status.assert_called()
    assert len(_calls_before(calls, start_idx, "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART")) >= 2
    assert len(_calls_before(calls, start_idx, "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE")) >= 2


def test_start_streaming_does_not_repause_when_media_at_zero(mock_obs_client):
    """位置ガード: media_cursor が0付近(既定)なら位置を確認するが余計な再送はしない。"""
    with patch('rct.obs_client.settings', make_settings(OBS_MEDIA_SOURCE_NAME='test_video.mp4')):
        with patch('rct.obs_client.time.sleep'):
            mock_obs_client.start_streaming()

    calls = mock_obs_client.client.method_calls
    names = [c[0] for c in calls]
    start_idx = names.index("start_stream")

    # ガードは位置を確認する（= get_media_input_status を呼ぶ）
    mock_obs_client.client.get_media_input_status.assert_called()
    # 0付近なので enable 後の1回のみ（再送なし）
    assert len(_calls_before(calls, start_idx, "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART")) == 1
    assert len(_calls_before(calls, start_idx, "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE")) == 1


def test_freeze_media_at_zero_sequence(mock_obs_client):
    """_freeze_media_at_zero: RESTART → 待機(settle) → PAUSE → cursor0 の順で確実に凍結する。

    OBS の RESTART は非同期で、待機なしに PAUSE を送ると再生が止まらない（実機確認）。
    この待機が頭切れ修正の核心。
    """
    from rct.obs_client import RESTART_SETTLE_SEC

    with patch('rct.obs_client.time.sleep') as mock_sleep:
        mock_obs_client._freeze_media_at_zero('test_video.mp4')

    actions = [
        c.args[1] for c in mock_obs_client.client.trigger_media_input_action.call_args_list
    ]
    assert actions == [
        "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART",
        "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE",
    ]
    # RESTART と PAUSE の間に settle 待機が1回入る
    mock_sleep.assert_called_once_with(RESTART_SETTLE_SEC)
    # 位置を厳密に0へ寄せる
    mock_obs_client.client.set_media_input_cursor.assert_called_once_with('test_video.mp4', 0)


def test_start_streaming_seeks_media_cursor_to_zero(mock_obs_client):
    """start_streaming は凍結時に set_media_input_cursor(source, 0) を呼ぶ。"""
    with patch('rct.obs_client.settings', make_settings(OBS_MEDIA_SOURCE_NAME='test_video.mp4')):
        with patch('rct.obs_client.time.sleep'):
            mock_obs_client.start_streaming()

    mock_obs_client.client.set_media_input_cursor.assert_any_call('test_video.mp4', 0)


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


# ------------------------------------------- ensure_media_file (動画選択機能)


def _resp_with_settings(settings_dict):
    """get_input_settings のレスポンスモック (input_settings 属性に dict)。"""
    resp = MagicMock()
    resp.input_settings = settings_dict
    return resp


def test_ensure_media_file_switches_when_path_differs(mock_obs_client):
    mock_obs_client.client.get_input_settings.return_value = _resp_with_settings(
        {"local_file": "/old.mp4"}
    )
    result = mock_obs_client.ensure_media_file("src", "/videos/new.mp4")
    assert result is True
    # overlay=True 必須: False だと looping / restart_on_activate 等が初期値に戻る
    mock_obs_client.client.set_input_settings.assert_called_once_with(
        "src", {"local_file": "/videos/new.mp4", "is_local_file": True}, True
    )


def test_ensure_media_file_noop_when_path_already_set(mock_obs_client):
    """毎朝 06:59 の通常ケース: 既に一致していれば書き込まない (冪等)。"""
    mock_obs_client.client.get_input_settings.return_value = _resp_with_settings(
        {"local_file": "/videos/new.mp4"}
    )
    result = mock_obs_client.ensure_media_file("src", "/videos/new.mp4")
    assert result is False
    mock_obs_client.client.set_input_settings.assert_not_called()


def test_ensure_media_file_returns_none_and_never_raises_on_error(mock_obs_client):
    """WS エラーでも例外を伝播させない (朝の自動配信を壊さないフェイルセーフ)。"""
    mock_obs_client.client.get_input_settings.side_effect = Exception("WS down")
    mock_obs_client.client.set_input_settings.side_effect = Exception("WS down")
    result = mock_obs_client.ensure_media_file("src", "/videos/new.mp4")
    assert result is None


def test_get_current_media_file_returns_local_file(mock_obs_client):
    mock_obs_client.client.get_input_settings.return_value = _resp_with_settings(
        {"local_file": "/v.mp4"}
    )
    assert mock_obs_client.get_current_media_file("src") == "/v.mp4"


def test_get_current_media_file_returns_none_on_error(mock_obs_client):
    mock_obs_client.client.get_input_settings.side_effect = Exception("WS down")
    assert mock_obs_client.get_current_media_file("src") is None


def test_start_streaming_ensures_media_file_before_freeze(mock_obs_client):
    """OBS_MEDIA_FILE_PATH 設定時、シーン準備後・凍結シーケンス前に local_file を同期する。

    凍結シーケンス (hide→show→RESTART→PAUSE→buffer→位置検証) がリロード後の
    メディアにかかるよう、差し替えは必ず凍結より前 (2026-06-10 頭切れ対策の保護)。
    """
    mock_obs_client.client.get_input_settings.return_value = _resp_with_settings(
        {"local_file": "/old.mp4"}
    )
    with patch('rct.obs_client.settings', make_settings(
        OBS_MEDIA_SOURCE_NAME='test_video.mp4', OBS_MEDIA_FILE_PATH='/videos/new.mp4'
    )):
        with patch('rct.obs_client.time.sleep'):
            mock_obs_client.start_streaming()

    names = [c[0] for c in mock_obs_client.client.method_calls]
    scene_idx = names.index("set_current_program_scene")
    set_input_idx = names.index("set_input_settings")
    first_enable_idx = names.index("set_scene_item_enabled")  # 凍結シーケンスの先頭 (hide)
    start_idx = names.index("start_stream")
    assert scene_idx < set_input_idx < first_enable_idx < start_idx


def test_start_streaming_skips_media_file_when_unset(mock_obs_client):
    """OBS_MEDIA_FILE_PATH 未設定なら従来動作と完全一致 (opt-in 保証)。"""
    with patch('rct.obs_client.settings', make_settings(
        OBS_MEDIA_SOURCE_NAME='test_video.mp4', OBS_MEDIA_FILE_PATH=None
    )):
        with patch('rct.obs_client.time.sleep'):
            mock_obs_client.start_streaming()

    mock_obs_client.client.set_input_settings.assert_not_called()
