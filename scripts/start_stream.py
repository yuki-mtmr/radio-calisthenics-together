#!/usr/bin/env python3
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from rct.obs_client import OBSClient
from rct.youtube_client import YouTubeClient
from rct.settings import settings
from rct.logger import setup_logger
from datetime import datetime

logger = setup_logger()

def main():
    logger.info("--- Starting Phase 2 Live Process ---")

    try:
        # 1. YouTube Live 枠の作成
        yt = YouTubeClient()
        now_str = datetime.now().strftime('%Y/%m/%d %H:%M')
        title = f"みんなでラジオ体操 ({now_str})"
        description = "毎朝の自動配信ラジオ体操です。今日も一日元気に過ごしましょう！"

        broadcast = yt.create_broadcast(title, description, privacy_status=settings.YOUTUBE_PRIVACY_STATUS)
        stream = yt.create_stream(f"Stream {now_str}")
        yt.bind_broadcast(broadcast['id'], stream['id'])

        stream_key = stream['cdn']['ingestionInfo']['streamName']
        logger.info(f"YouTube Broadcast created. ID: {broadcast['id']}")

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

        if obs.start_streaming():
            logger.info("Phase 2 automation completed successfully.")
        else:
            logger.error("Failed to start OBS stream.")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Phase 2 error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
