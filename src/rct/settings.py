import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Settings:
    OBS_WS_HOST = os.getenv("OBS_WS_HOST", "127.0.0.1")
    OBS_WS_PORT = int(os.getenv("OBS_WS_PORT", "4455"))
    OBS_WS_PASSWORD = os.getenv("OBS_WS_PASSWORD", "")

    OBS_SCENE_NAME = os.getenv("OBS_SCENE_NAME", "RADIO_TAISO_LOOP")
    OBS_PROFILE_NAME = os.getenv("OBS_PROFILE_NAME", None)

    LOG_DIR = os.getenv("LOG_DIR", "./logs")
    START_RETRIES = int(os.getenv("START_RETRIES", "3"))
    RETRY_DELAY = int(os.getenv("RETRY_DELAY", "5"))

    OBS_PATH = os.getenv("OBS_PATH", "/Applications/OBS.app/Contents/MacOS/OBS")

settings = Settings()
