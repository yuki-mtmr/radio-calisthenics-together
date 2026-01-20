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

def main():
    logger.info("--- Starting Phase 2 Live Process ---")

    try:
        # 1. YouTube Live 枠の作成 または 既存枠の検索
        yt = YouTubeClient()
        now = datetime.now()
        now_date_str = now.strftime('%Y/%m/%d')
        target_title = f"みんなでラジオ体操 ({now_date_str}" # 部分一致で検索

        upcoming = yt.list_upcoming_broadcasts()
        broadcast = None
        for item in upcoming:
            if target_title in item['snippet']['title']:
                broadcast = item
                logger.info(f"Found existing upcoming broadcast: {broadcast['snippet']['title']}")
                break

        if not broadcast:
            now_dt = datetime.now()
            title = f"みんなでラジオ体操 ({now_dt.strftime('%Y/%m/%d %H:%M')})"
            description = "毎朝の自動配信ラジオ体操です。今日も一日元気に過ごしましょう！"

            # 1分後の開始として枠を作成
            start_iso = (datetime.utcnow() + timedelta(minutes=1)).isoformat() + 'Z'
            broadcast = yt.create_broadcast(title, description, start_time_iso=start_iso, privacy_status=settings.YOUTUBE_PRIVACY_STATUS)
            logger.info(f"New YouTube Broadcast created. ID: {broadcast['id']}")

        # ストリームは毎回作成してバインド（既存ストリームの再利用が難しいため）
        stream = yt.create_stream(f"Stream {now.strftime('%H:%M:%S')}")
        yt.bind_broadcast(broadcast['id'], stream['id'])

        stream_key = stream['cdn']['ingestionInfo']['streamName']

        # 2. OBS の制御
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

        # --- 開始時刻まで待機 (ちょうどに始めるための調整) ---
        try:
            target_h, target_m = settings.STREAM_START_TIME.split(':')
            target_dt = datetime.now().replace(hour=int(target_h), minute=int(target_m), second=0, microsecond=0)

            # もし現在時刻がターゲットより前なら、その差分だけ待つ
            # YouTube側のラグを考慮し、10秒早めにOBSの配信を開始する
            wait_seconds = (target_dt - datetime.now()).total_seconds() - 10
            if wait_seconds > 0:
                logger.info(f"Waiting {wait_seconds:.1f} seconds to start a bit early (10s buffer)...")
                time.sleep(wait_seconds)
            else:
                 logger.info("Skipping wait (already past target start time minus 10s).")

        except Exception as e:
            logger.warning(f"Wait logic skipped due to error: {e}")

        # 明示的にシーンアイテムを表示状態にする（自動再生されない問題への対策）
        # start_streaming内でもリフレッシュは行うが、念のためここでも確認
        obs.connect() # 接続確保
        if settings.OBS_MEDIA_SOURCE_NAME:
            try:
                obs.set_scene_item_enabled(settings.OBS_SCENE_NAME, settings.OBS_MEDIA_SOURCE_NAME, True)
            except Exception as e:
                logger.warning(f"Failed to ensure media source visibility: {e}")

        if obs.start_streaming():
            logger.info("Phase 2 automation completed successfully.")
        else:
            logger.error("Failed to start OBS stream.")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Phase 2 error: {e}")
        send_alert_email("Broadcast Start Failed", f"An error occurred during Phase 2 auto-start:\n\n{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
