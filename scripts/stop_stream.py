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

logger = setup_logger()

def main():
    logger.info("--- Stopping Stream Process ---")
    client = OBSClient()

    if not client.connect():
        logger.error("Could not connect to OBS. It might not be running.")
        sys.exit(0) # Exit gracefully if OBS is already closed

    if client.stop_streaming():
        logger.info("Stop stream sequence completed successfully.")
    else:
        logger.error("Stop stream sequence failed.")

    # 翌日の枠を予約する（24時間前予約の実現）
    try:
        yt = YouTubeClient()
        now = datetime.now()

        # --- クリーンアップ：もし「今日」の予定枠が残っていたら削除する ---
        today_str = now.strftime('%Y/%m/%d')
        today_item = yt.find_broadcast_by_date(today_str)
        if today_item:
            logger.info(f"Today's leftover broadcast found ({today_item['id']}). Deleting...")
            yt.delete_broadcast(today_item['id'])

        # --- 翌日の予約作成 ---
        tomorrow = now + timedelta(days=1)
        next_date_str = tomorrow.strftime('%Y/%m/%d')

        # 既に翌日の予約があるかチェック
        tomorrow_item = yt.find_broadcast_by_date(next_date_str)
        if tomorrow_item:
            logger.info(f"Broadcast for tomorrow ({next_date_str}) already exists ({tomorrow_item['id']}). Skipping creation.")
            return

        logger.info("Scheduling next day's broadcast...")
        # 設定された開始時刻を取得 (例: "07:00")
        start_h, start_m = settings.STREAM_START_TIME.split(':')

        # JSTの開始時刻を作成
        next_start_jst = tomorrow.replace(hour=int(start_h), minute=int(start_m), second=0, microsecond=0)

        # YouTube API用にUTCに変換（JST - 9時間）
        next_start_utc = next_start_jst - timedelta(hours=9)
        next_start_iso = next_start_utc.isoformat() + 'Z'

        title = f"みんなでラジオ体操 ({next_date_str} {settings.STREAM_START_TIME})"
        description = "毎朝の自動配信ラジオ体操です。今日も一日元気に過ごしましょう！"

        yt.create_broadcast(title, description, start_time_iso=next_start_iso, privacy_status=settings.YOUTUBE_PRIVACY_STATUS)
        logger.info(f"Broadcast for tomorrow ({next_date_str} {settings.STREAM_START_TIME}) scheduled successfully.")

    except Exception as e:
        logger.error(f"Failed to schedule tomorrow's broadcast: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
