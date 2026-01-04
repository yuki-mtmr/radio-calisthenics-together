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

settings = Settings()
