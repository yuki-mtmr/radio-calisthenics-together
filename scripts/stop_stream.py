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


def stop_obs_streaming():
    """OBS の配信を停止する。失敗してもログのみで例外は投げない。"""
    client = OBSClient()
    if not client.connect():
        logger.error("Could not connect to OBS. It might not be running.")
        return False
    if client.stop_streaming():
        logger.info("Stop stream sequence completed successfully.")
        return True
    logger.error("Stop stream sequence failed.")
    return False


def _tomorrow_start_iso(tomorrow: datetime, start_time_str: str) -> str:
    """翌日の配信開始時刻を UTC ISO 文字列で返す (JST -9h 変換)。

    引数:
        tomorrow: 翌日の datetime (時刻は任意、date 部分のみ使用)
        start_time_str: "HH:MM" 形式の JST 開始時刻
    """
    start_h, start_m = start_time_str.split(':')
    next_start_jst = tomorrow.replace(hour=int(start_h), minute=int(start_m), second=0, microsecond=0)
    next_start_utc = next_start_jst - timedelta(hours=9)
    return next_start_utc.isoformat() + 'Z'


def schedule_tomorrow_broadcast():
    """翌日の YouTube 配信枠を予約する。今日の残骸枠があれば削除する。"""
    yt = YouTubeClient()
    now = datetime.now()

    today_str = now.strftime('%Y/%m/%d')
    today_item = yt.find_broadcast_by_date(today_str)
    if today_item:
        logger.info(f"Today's leftover broadcast found ({today_item['id']}). Deleting...")
        yt.delete_broadcast(today_item['id'])

    tomorrow = now + timedelta(days=1)
    next_date_str = tomorrow.strftime('%Y/%m/%d')

    tomorrow_item = yt.find_broadcast_by_date(next_date_str)
    if tomorrow_item:
        logger.info(f"Broadcast for tomorrow ({next_date_str}) already exists ({tomorrow_item['id']}). Skipping creation.")
        return

    logger.info("Scheduling next day's broadcast...")
    next_start_iso = _tomorrow_start_iso(tomorrow, settings.STREAM_START_TIME)

    title = f"みんなでラジオ体操 ({next_date_str} {settings.STREAM_START_TIME})"
    description = "毎朝の自動配信ラジオ体操です。今日も一日元気に過ごしましょう！"

    yt.create_broadcast(title, description, start_time_iso=next_start_iso, privacy_status=settings.YOUTUBE_PRIVACY_STATUS)
    logger.info(f"Broadcast for tomorrow ({next_date_str} {settings.STREAM_START_TIME}) scheduled successfully.")


def main():
    logger.info("--- Stopping Stream Process ---")

    # OBS 停止と翌日予約は独立に実行する。
    # 2026-05-17 インシデント: OBS 接続失敗で sys.exit(0) し翌日予約が走らなかった。
    stop_obs_streaming()

    try:
        schedule_tomorrow_broadcast()
    except Exception as e:
        logger.error(f"Failed to schedule tomorrow's broadcast: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
