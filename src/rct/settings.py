import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Settings:
    OBS_WS_HOST = os.getenv("OBS_WS_HOST", "127.0.0.1")
    OBS_WS_PORT = int(os.getenv("OBS_WS_PORT", "4455"))
    OBS_WS_PASSWORD = os.getenv("OBS_WS_PASSWORD", "")

    OBS_SCENE_NAME = os.getenv("OBS_SCENE_NAME", "RADIO_TAISO_LOOP")
    OBS_MEDIA_SOURCE_NAME = os.getenv("OBS_MEDIA_SOURCE_NAME", None)
    OBS_PROFILE_NAME = os.getenv("OBS_PROFILE_NAME", None)

    LOG_DIR = os.getenv("LOG_DIR", "./logs")
    YOUTUBE_PRIVACY_STATUS = os.getenv("YOUTUBE_PRIVACY_STATUS", "public")
    YOUTUBE_RESERVATION_BUFFER_MINUTES = int(os.getenv("YOUTUBE_RESERVATION_BUFFER_MINUTES", "2"))
    STREAM_START_TIME = os.getenv("STREAM_START_TIME", "07:00")
    STREAM_STOP_TIME = os.getenv("STREAM_STOP_TIME", "07:05")

    ALERT_EMAIL_SENDER = os.getenv("ALERT_EMAIL_SENDER", "")
    ALERT_EMAIL_PASSWORD = os.getenv("ALERT_EMAIL_PASSWORD", "")
    ALERT_EMAIL_RECEIVER = os.getenv("ALERT_EMAIL_RECEIVER", "")

settings = Settings()
