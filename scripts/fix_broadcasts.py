import os
import sys
from datetime import datetime, timedelta

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from rct.youtube_client import YouTubeClient
from rct.settings import settings
from rct.logger import setup_logger

logger = setup_logger()

def fix_upcoming_broadcasts():
    logger.info("--- Fixing existing upcoming broadcasts ---")
    yt = YouTubeClient()
    upcoming = yt.list_upcoming_broadcasts()

    if not upcoming:
        logger.info("No upcoming broadcasts found.")
        return

    # ターゲットの日付（今日と明日）
    today = datetime.now()
    dates_to_fix = [today, today + timedelta(days=1)]

    for target_date in dates_to_fix:
        date_str = target_date.strftime('%Y/%m/%d')
        start_h, start_m = settings.STREAM_START_TIME.split(':')

        # 正しい開始時刻 (JST)
        correct_start_jst = target_date.replace(hour=int(start_h), minute=int(start_m), second=0, microsecond=0)
        correct_start_utc = correct_start_jst - timedelta(hours=9)
        correct_start_iso = correct_start_utc.isoformat() + 'Z'

        for item in upcoming:
            # 既に存在する枠のうち、その日のもの
            if date_str in item['snippet']['title']:
                broadcast_id = item['id']
                logger.info(f"Updating broadcast {broadcast_id} ('{item['snippet']['title']}') to {settings.STREAM_START_TIME}...")

                # スケジュールを更新
                try:
                    body = {
                        'id': broadcast_id,
                        'snippet': {
                            'title': f"みんなでラジオ体操 ({date_str} {settings.STREAM_START_TIME})",
                            'scheduledStartTime': correct_start_iso
                        }
                    }
                    yt.youtube.liveBroadcasts().update(part='snippet', body=body).execute()
                    logger.info(f"Successfully updated {broadcast_id}")
                except Exception as e:
                    logger.error(f"Failed to update {broadcast_id}: {e}")

if __name__ == "__main__":
    fix_upcoming_broadcasts()
