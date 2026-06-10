"""頭切れ hotfix (2026-06-10) の仕様テスト — 定刻アンカー方式。

毎朝 6〜30 秒の頭切れの原因 (2026-06-03〜06-10 の actualStartTime で実測):
- PLAY が「OBS 送出開始 +0.5s」起点で、YouTube autoStart の live 遷移
  (日次 3〜27s 変動) を一切待たない
- 「10 秒前倒し」バッファが媒体凍結シーケンス約 6.4s に食われ実質 3.6s

対策:
1. 送出開始を定刻 PRE_START_LEAD_SEC 秒前に前倒し (resume_media=False で凍結維持)
2. lifeCycleStatus == 'live' をポーリング確認 (API エラーは握り潰して継続)
3. 定刻に resume_media_playback() で位置 0 から再生開始

既存互換:
- start_streaming() のデフォルト (resume_media=True) は完全に従来挙動
  → tests/test_obs_client.py の 14 テストは無編集で緑のまま
- _setup_youtube_broadcast は (broadcast, stream_key, yt) の 3-tuple を返す
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_settings


class _SleepRecorder:
    def __init__(self):
        self.calls = []

    def __call__(self, seconds):
        self.calls.append(seconds)


# ------------------------------------------------------------------ obs_client


@pytest.fixture
def obs():
    with patch("obsws_python.ReqClient"):
        from rct.obs_client import OBSClient

        c = OBSClient()
        c.client = MagicMock()
        c.connect = MagicMock(return_value=True)
        status = MagicMock()
        status.output_active = False
        c.client.get_stream_status.return_value = status
        media = MagicMock()
        media.media_cursor = 0
        media.media_state = "OBS_MEDIA_STATE_PAUSED"
        c.client.get_media_input_status.return_value = media
        yield c


def _actions(c):
    return [call.args[1] for call in c.client.trigger_media_input_action.call_args_list]


def test_start_streaming_resume_media_false_keeps_media_frozen(obs):
    """resume_media=False では凍結 (RESTART→PAUSE) まで行い PLAY を送らない。"""
    with patch("rct.obs_client.settings", make_settings(OBS_MEDIA_SOURCE_NAME="vid.mp4")), \
         patch("rct.obs_client.time.sleep"):
        assert obs.start_streaming(resume_media=False) is True

    actions = _actions(obs)
    assert "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART" in actions
    assert "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE" in actions
    assert "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY" not in actions
    obs.client.start_stream.assert_called_once()


def test_start_streaming_default_still_plays(obs):
    """デフォルト (resume_media 省略) は従来通り PLAY まで行う。"""
    with patch("rct.obs_client.settings", make_settings(OBS_MEDIA_SOURCE_NAME="vid.mp4")), \
         patch("rct.obs_client.time.sleep"):
        assert obs.start_streaming() is True

    assert "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY" in _actions(obs)


def test_resume_media_playback_sends_play(obs):
    """resume_media_playback は PLAY を送り True を返す。"""
    assert obs.resume_media_playback("vid.mp4") is True
    obs.client.trigger_media_input_action.assert_called_once_with(
        "vid.mp4", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY"
    )


def test_resume_media_playback_swallows_errors(obs):
    """PLAY 失敗は False を返すのみで例外を上げない (配信自体は継続させる)。"""
    obs.client.trigger_media_input_action.side_effect = Exception("ws down")
    assert obs.resume_media_playback("vid.mp4") is False


# ---------------------------------------------------------------- start_stream


def _live_resp(status):
    return {"items": [{"status": {"lifeCycleStatus": status}}]}


def _yt_with_statuses(statuses):
    yt = MagicMock()
    yt.youtube.liveBroadcasts.return_value.list.return_value.execute.side_effect = list(statuses)
    return yt


def test_lead_constants():
    """前倒し幅とポーリング設定の凍結値。"""
    import scripts.start_stream as ss

    assert ss.PRE_START_LEAD_SEC == 45
    assert ss.LIVE_POLL_INTERVAL_SEC == 2
    assert ss.LIVE_POLL_MAX_POLLS == 60


def test_wait_for_broadcast_live_polls_until_live():
    """ready → ready → live で True。失敗 2 回分のみ sleep。"""
    from scripts.start_stream import _wait_for_broadcast_live

    yt = _yt_with_statuses([_live_resp("ready"), _live_resp("ready"), _live_resp("live")])
    sleep = _SleepRecorder()
    target = datetime(2026, 6, 11, 7, 0, 0)
    fixed_now = datetime(2026, 6, 11, 6, 59, 25)

    assert _wait_for_broadcast_live(
        yt, "bid", target, now_fn=lambda: fixed_now, sleep_fn=sleep
    ) is True
    assert sleep.calls == [2, 2]


def test_wait_for_broadcast_live_gives_up_at_target_time():
    """定刻を過ぎていたら API を呼ばず即 False (定刻 PLAY を遅らせない)。"""
    from scripts.start_stream import _wait_for_broadcast_live

    yt = MagicMock()
    target = datetime(2026, 6, 11, 7, 0, 0)
    after_target = datetime(2026, 6, 11, 7, 0, 1)

    assert _wait_for_broadcast_live(
        yt, "bid", target, now_fn=lambda: after_target, sleep_fn=_SleepRecorder()
    ) is False
    yt.youtube.liveBroadcasts.return_value.list.assert_not_called()


def test_wait_for_broadcast_live_survives_api_errors():
    """ポーリング中の API エラーは握り潰して継続 (2026-05-18 DNS 瞬断の前例)。"""
    from scripts.start_stream import _wait_for_broadcast_live

    yt = _yt_with_statuses([Exception("dns blip"), _live_resp("live")])
    sleep = _SleepRecorder()
    fixed_now = datetime(2026, 6, 11, 6, 59, 25)

    assert _wait_for_broadcast_live(
        yt, "bid", datetime(2026, 6, 11, 7, 0, 0),
        now_fn=lambda: fixed_now, sleep_fn=sleep,
    ) is True
    assert sleep.calls == [2]


def test_wait_for_broadcast_live_hard_cap_prevents_spin():
    """live にならず時計も進まない場合でも LIVE_POLL_MAX_POLLS 回で必ず諦める。"""
    import scripts.start_stream as ss

    yt = MagicMock()
    yt.youtube.liveBroadcasts.return_value.list.return_value.execute.return_value = _live_resp("ready")
    sleep = _SleepRecorder()
    fixed_now = datetime(2026, 6, 11, 6, 59, 25)

    assert ss._wait_for_broadcast_live(
        yt, "bid", datetime(2026, 6, 11, 7, 0, 0),
        now_fn=lambda: fixed_now, sleep_fn=sleep,
    ) is False
    assert len(sleep.calls) == ss.LIVE_POLL_MAX_POLLS


def test_setup_youtube_broadcast_returns_client():
    """_setup_youtube_broadcast は (broadcast, stream_key, yt) を返す (ポーリングで再利用)。"""
    with patch("scripts.start_stream.YouTubeClient") as mock_cls:
        yt = mock_cls.return_value
        yt.list_upcoming_broadcasts.return_value = []
        yt.create_broadcast.return_value = {"id": "bid"}
        yt.create_stream.return_value = {
            "id": "sid",
            "cdn": {"ingestionInfo": {"streamName": "key"}},
        }

        from scripts.start_stream import _setup_youtube_broadcast

        broadcast, stream_key, returned_yt = _setup_youtube_broadcast()

        assert broadcast["id"] == "bid"
        assert stream_key == "key"
        assert returned_yt is yt


def test_main_starts_frozen_then_waits_live_then_resumes():
    """main の配線: start_streaming(resume_media=False) → live 待ち → 定刻 PLAY の順。"""
    with patch("scripts.start_stream._is_already_broadcasting", return_value=False), \
         patch("scripts.start_stream.YouTubeClient") as mock_yt_cls, \
         patch("scripts.start_stream.OBSClient") as mock_obs_cls, \
         patch("scripts.start_stream.settings") as mock_settings, \
         patch("scripts.start_stream._wait_for_broadcast_live") as mock_wait, \
         patch("scripts.start_stream.time.sleep"):

        mock_settings.STREAM_START_TIME = "07:00"
        mock_settings.YOUTUBE_PRIVACY_STATUS = "public"
        mock_settings.OBS_MEDIA_SOURCE_NAME = "vid.mp4"
        mock_settings.OBS_SCENE_NAME = "scene"

        yt = mock_yt_cls.return_value
        yt.list_upcoming_broadcasts.return_value = []
        yt.create_broadcast.return_value = {"id": "bid"}
        yt.create_stream.return_value = {
            "id": "sid",
            "cdn": {"ingestionInfo": {"streamName": "key"}},
        }

        mock_obs = MagicMock()
        mock_obs.start_streaming.return_value = True
        mock_obs_cls.return_value = mock_obs

        from scripts.start_stream import main

        main()

        # 凍結维持で送出開始
        assert mock_obs.start_streaming.call_args.kwargs.get("resume_media") is False
        # live 遷移を broadcast id 付きで待つ
        mock_wait.assert_called_once()
        assert mock_wait.call_args[0][1] == "bid"
        # PLAY は start_streaming の後
        mock_obs.resume_media_playback.assert_called_once_with("vid.mp4")
        names = [c[0] for c in mock_obs.method_calls]
        assert names.index("start_streaming") < names.index("resume_media_playback")
