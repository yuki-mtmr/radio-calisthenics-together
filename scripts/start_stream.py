#!/usr/bin/env python3
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from rct.obs_client import OBSClient
from rct.youtube_client import YouTubeClient
from rct.settings import settings
from rct.logger import setup_logger
from datetime import datetime, timedelta
import time
from rct.notify import send_alert_email

logger = setup_logger()

# 2026-05-18 インシデント: 06:46 に DNS/ネット瞬断で youtube.googleapis.com 名前解決失敗
YOUTUBE_RETRIES = 3
YOUTUBE_RETRY_DELAY = 5

# 定刻アンカー方式 (2026-06-10 頭切れ対策)
# OBS 送出を定刻 PRE_START_LEAD_SEC 秒前に開始し、YouTube の live 遷移を確認してから
# 定刻ちょうどに位置0で PLAY する。autoStart 遷移ラグ (日次 3〜27s) を吸収する。
PRE_START_LEAD_SEC = 45        # 送出前倒し幅 (凍結維持で送出 → live 待ち)
LIVE_POLL_INTERVAL_SEC = 2     # lifeCycleStatus ポーリング間隔
LIVE_POLL_MAX_POLLS = 60       # ポーリング上限 (= 120 秒、定刻超過ガードが先に発動する想定)


def _find_or_create_broadcast(yt, now: datetime):
    """当日の upcoming 枠を探し、なければ作成して返す。"""
    now_date_str = now.strftime('%Y/%m/%d')
    target_title = f"みんなでラジオ体操 ({now_date_str}"

    for item in yt.list_upcoming_broadcasts():
        if target_title in item['snippet']['title']:
            logger.info(f"Found existing upcoming broadcast: {item['snippet']['title']}")
            return item

    title = f"みんなでラジオ体操 ({now.strftime('%Y/%m/%d %H:%M')})"
    description = "毎朝の自動配信ラジオ体操です。今日も一日元気に過ごしましょう！"
    start_iso = (datetime.utcnow() + timedelta(minutes=1)).isoformat() + 'Z'
    broadcast = yt.create_broadcast(title, description, start_time_iso=start_iso, privacy_status=settings.YOUTUBE_PRIVACY_STATUS)
    logger.info(f"New YouTube Broadcast created. ID: {broadcast['id']}")
    return broadcast


def _setup_youtube_broadcast():
    """YouTube broadcast + stream をリトライ付きで準備する。

    戻り値: (broadcast, stream_key, yt) — yt は live 遷移ポーリングで再利用。
    """
    last_exc = None
    for attempt in range(YOUTUBE_RETRIES):
        try:
            yt = YouTubeClient()
            now = datetime.now()
            broadcast = _find_or_create_broadcast(yt, now)
            stream = yt.create_stream(f"Stream {now.strftime('%H:%M:%S')}")
            yt.bind_broadcast(broadcast['id'], stream['id'])
            stream_key = stream['cdn']['ingestionInfo']['streamName']
            return broadcast, stream_key, yt
        except Exception as e:
            last_exc = e
            logger.warning(f"YouTube setup attempt {attempt + 1}/{YOUTUBE_RETRIES} failed: {e}")
            if attempt < YOUTUBE_RETRIES - 1:
                logger.info(f"Retrying in {YOUTUBE_RETRY_DELAY}s...")
                time.sleep(YOUTUBE_RETRY_DELAY)
    raise last_exc


def _wait_for_broadcast_live(yt, broadcast_id, target_dt, now_fn=None, sleep_fn=None):
    """YouTube の lifeCycleStatus が 'live' になるまでポーリングする。

    - 定刻 (target_dt) を過ぎたら即 False を返して PLAY を遅らせない
    - API エラーは握り潰して継続 (DNS 瞬断の前例あり)
    - LIVE_POLL_MAX_POLLS に達したら False (定刻ガードが先に発動する想定)
    """
    _now = now_fn if now_fn is not None else datetime.now
    _sleep = sleep_fn if sleep_fn is not None else time.sleep

    for _ in range(LIVE_POLL_MAX_POLLS):
        if _now() >= target_dt:
            logger.info("Target time reached while polling; proceeding to PLAY.")
            return False
        try:
            resp = yt.youtube.liveBroadcasts().list(
                part='status', id=broadcast_id
            ).execute()
            if resp['items'][0]['status']['lifeCycleStatus'] == 'live':
                logger.info("Broadcast is live. Proceeding to PLAY.")
                return True
        except Exception as e:
            logger.debug(f"lifeCycleStatus poll error (continuing): {e}")
        _sleep(LIVE_POLL_INTERVAL_SEC)

    logger.warning("Broadcast did not go live within poll cap; proceeding to PLAY.")
    return False


def _is_already_broadcasting():
    """orchestrator や verify_stream が先に start を呼んだ場合の重複起動防止。

    YouTube API の active broadcast 一覧に「みんなでラジオ体操」を含むタイトルが
    あれば True。API 呼び出しが失敗したらフォールバックして False (既存フローに任せる)。
    """
    try:
        yt = YouTubeClient()
        for item in yt.list_active_broadcasts():
            title = item.get("snippet", {}).get("title", "")
            if "みんなでラジオ体操" in title:
                return True
        return False
    except Exception as e:
        logger.warning(f"_is_already_broadcasting check failed: {e}")
        return False


def main():
    logger.info("--- Starting Phase 2 Live Process ---")

    if _is_already_broadcasting():
        logger.info("Already broadcasting. Skipping duplicate start.")
        return

    try:
        broadcast, stream_key, yt = _setup_youtube_broadcast()

        # OBS の制御
        obs = OBSClient()

        # 必要なら OBS のストリームキーを更新 (WebSocket経由)
        # ※OBS側の設定で「配信キーを使用」モードになっている必要があります
        try:
            obs.connect()
            obs.client.set_stream_service_settings(
                "rtmp_custom", # または "rtmp_common"
                {
                    "key": stream_key,
                    "server": "rtmp://a.rtmp.youtube.com/live2"
                }
            )
            logger.info("OBS Stream Key updated via WebSocket.")
        except Exception as e:
            logger.warning(f"Could not update OBS Stream Key automatically: {e}")
            logger.warning("Please ensure OBS is set to 'Custom' or 'YouTube - RTMP' with stream key usage.")

        # --- 定刻 PRE_START_LEAD_SEC 秒前まで待機 ---
        target_dt = None
        try:
            target_h, target_m = settings.STREAM_START_TIME.split(':')
            target_dt = datetime.now().replace(
                hour=int(target_h), minute=int(target_m), second=0, microsecond=0
            )
            wait_seconds = (target_dt - datetime.now()).total_seconds() - PRE_START_LEAD_SEC
            if wait_seconds > 0:
                logger.info(f"Waiting {wait_seconds:.1f}s to start {PRE_START_LEAD_SEC}s early (live anchor)...")
                time.sleep(wait_seconds)
            else:
                logger.info("Skipping pre-start wait (already within lead window).")
        except Exception as e:
            logger.warning(f"Wait logic skipped due to error: {e}")

        # 明示的にシーンアイテムを表示状態にする（自動再生されない問題への対策）
        # start_streaming内でもリフレッシュは行うが、念のためここでも確認
        obs.connect()  # 接続確保
        if settings.OBS_MEDIA_SOURCE_NAME:
            try:
                obs.set_scene_item_enabled(settings.OBS_SCENE_NAME, settings.OBS_MEDIA_SOURCE_NAME, True)
            except Exception as e:
                logger.warning(f"Failed to ensure media source visibility: {e}")

        # 凍結維持で送出開始 → live 遷移を待ってから定刻に PLAY
        if not obs.start_streaming(resume_media=False):
            logger.error("Failed to start OBS stream.")
            sys.exit(1)

        if target_dt is not None:
            # YouTube の live 遷移をポーリング
            _wait_for_broadcast_live(yt, broadcast['id'], target_dt)

            # 定刻まで残り時間があれば待つ
            remaining = (target_dt - datetime.now()).total_seconds()
            if remaining > 0:
                logger.info(f"Waiting {remaining:.1f}s until target time for PLAY...")
                time.sleep(remaining)

        # 定刻に位置0から再生開始
        if settings.OBS_MEDIA_SOURCE_NAME:
            obs.resume_media_playback(settings.OBS_MEDIA_SOURCE_NAME)

        logger.info("Phase 2 automation completed successfully.")

    except Exception as e:
        logger.error(f"Phase 2 error: {e}")
        try:
            send_alert_email("Broadcast Start Failed", f"An error occurred during Phase 2 auto-start:\n\n{e}")
        except Exception as email_err:
            logger.error(f"Email notification failed: {email_err}")
        sys.exit(1)

if __name__ == "__main__":
    main()
