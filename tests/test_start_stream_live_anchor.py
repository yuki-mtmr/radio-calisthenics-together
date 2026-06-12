"""頭切れ対策の仕様テスト — live 即時 PLAY + grace 方式 (2026-06-12 改訂)。

経緯:
- 2026-06-10: 定刻アンカー方式を導入 (送出 45s 前倒し + 定刻 07:00 に PLAY)。
  頭切れ (日次 3〜27s の autoStart 遷移ラグ) はゼロになったが、
  live 化から定刻までの静止フレームが VOD 冒頭に最大 ~40s 残った (06-12 朝に顕在化)。
- 2026-06-12: live 検知で即 PLAY に変更 (ユーザー決定: 開始時刻 ±15s のブレを許容し、
  VOD 冒頭の静止を ~2〜4s にする)。

現仕様:
1. 送出開始を定刻 PRE_START_LEAD_SEC(=15) 秒前に前倒し (resume_media=False で凍結維持)
2. lifeCycleStatus == 'live' をポーリング (API エラーは握り潰して継続)。
   定刻を過ぎても LIVE_GRACE_AFTER_TARGET_SEC(=45) 秒までは live を待つ (頭切れ防止の本体)
3. live 検知したら**即** resume_media_playback() (定刻まで待たない)
4. grace デッドライン超過 / ポーリング上限で諦めて PLAY (lock を 07:01 の verify より
   前に必ず解放するため。無期限に待つと verify のリトライが AlreadyRunning で空振りする)

既存互換:
- start_streaming() のデフォルト (resume_media=True) は完全に従来挙動
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
    """前倒し幅・grace・ポーリング設定の凍結値。

    PRE_START_LEAD_SEC=15: live 化が定刻近傍に来るよう短縮 (45 だと最大 ~40s 早く始まる)。
    LIVE_GRACE_AFTER_TARGET_SEC=45: 観測最大ラグ 27s の ~1.7 倍。lock を 07:01 の
    verify より前に解放するため、これを超えては待たない。
    """
    import scripts.start_stream as ss

    assert ss.PRE_START_LEAD_SEC == 15
    assert ss.LIVE_GRACE_AFTER_TARGET_SEC == 45
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


def test_wait_for_broadcast_live_keeps_polling_past_target_until_live():
    """定刻を過ぎても grace 内なら live を待ち続ける (頭切れ防止の本体)。

    旧仕様は定刻で即 False → 呼び出し側が live 前に PLAY → ラグが大きい日に頭切れ。
    新仕様は定刻後も polling を継続し、live 検知で True を返す。
    """
    from scripts.start_stream import _wait_for_broadcast_live

    yt = _yt_with_statuses([_live_resp("ready"), _live_resp("live")])
    sleep = _SleepRecorder()
    target = datetime(2026, 6, 12, 7, 0, 0)
    past_target = datetime(2026, 6, 12, 7, 0, 10)  # 定刻 +10s (grace 45s 内)

    assert _wait_for_broadcast_live(
        yt, "bid", target, now_fn=lambda: past_target, sleep_fn=sleep
    ) is True
    assert sleep.calls == [2]


def test_wait_for_broadcast_live_gives_up_at_grace_deadline():
    """定刻 + LIVE_GRACE_AFTER_TARGET_SEC を過ぎたら API を呼ばず即 False。

    lock を 07:01 の verify リトライより前に解放するための上限 (無期限に待たない)。
    """
    import scripts.start_stream as ss

    yt = MagicMock()
    target = datetime(2026, 6, 12, 7, 0, 0)
    at_deadline = target + timedelta(seconds=ss.LIVE_GRACE_AFTER_TARGET_SEC)

    assert ss._wait_for_broadcast_live(
        yt, "bid", target, now_fn=lambda: at_deadline, sleep_fn=_SleepRecorder()
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


def test_main_plays_immediately_after_live_detection():
    """live 検知後は定刻まで待たずに即 PLAY する (検知と PLAY の間に sleep が入らない)。

    STREAM_START_TIME=23:59 が決定的 RED の肝: 旧仕様 (定刻アンカー) だと live 検知後に
    23:59 まで sleep(remaining) が入り本テストが fail する。テスト実行時刻に依存しない。
    """
    live_detected = {"flag": False}

    def fake_wait(*args, **kwargs):
        live_detected["flag"] = True
        return True

    def sleep_guard(seconds):
        assert not live_detected["flag"], (
            f"live 検知後に sleep({seconds}) が呼ばれた (即 PLAY 違反)"
        )

    with patch("scripts.start_stream._is_already_broadcasting", return_value=False), \
         patch("scripts.start_stream.YouTubeClient") as mock_yt_cls, \
         patch("scripts.start_stream.OBSClient") as mock_obs_cls, \
         patch("scripts.start_stream.settings") as mock_settings, \
         patch("scripts.start_stream._wait_for_broadcast_live", side_effect=fake_wait), \
         patch("scripts.start_stream.send_alert_email"), \
         patch("scripts.start_stream.time.sleep", side_effect=sleep_guard):

        mock_settings.STREAM_START_TIME = "23:59"
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

        mock_obs.resume_media_playback.assert_called_once_with("vid.mp4")


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
