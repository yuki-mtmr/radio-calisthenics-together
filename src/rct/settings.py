from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from dotenv import load_dotenv

# import 時に .env を読み込む (既存の挙動を維持)
load_dotenv()


@dataclass(frozen=True)
class Settings:
    OBS_WS_HOST: str = "127.0.0.1"
    OBS_WS_PORT: int = 4455
    OBS_WS_PASSWORD: str = ""

    OBS_SCENE_NAME: str = "RADIO_TAISO_LOOP"
    OBS_MEDIA_SOURCE_NAME: str | None = None
    OBS_PROFILE_NAME: str | None = None
    # 配信動画のホスト絶対パス (OBS=ホストプロセスが開くため)。
    # None/空なら従来どおり OBS 内の設定をそのまま使う (opt-in)。
    OBS_MEDIA_FILE_PATH: str | None = None

    LOG_DIR: str = "./logs"
    YOUTUBE_PRIVACY_STATUS: str = "public"
    YOUTUBE_RESERVATION_BUFFER_MINUTES: int = 2
    STREAM_START_TIME: str = "07:00"
    STREAM_STOP_TIME: str = "07:05"

    ALERT_EMAIL_SENDER: str = ""
    ALERT_EMAIL_PASSWORD: str = ""
    ALERT_EMAIL_RECEIVER: str = ""

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587

    # ディスク空き容量ガード (2026-08-06 ENOSPC 事故由来)
    # CRITICAL 未満: 配信前に中断 / WARN 未満: 通知するが続行
    DISK_FREE_CRITICAL_GB: int = 5
    DISK_FREE_WARN_GB: int = 20


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """環境変数 (デフォルト os.environ) から Settings を生成する。"""
    e = env if env is not None else os.environ

    def _str(key: str, default: str) -> str:
        return e.get(key, default)

    def _int(key: str, default: int) -> int:
        v = e.get(key)
        return int(v) if v is not None else default

    def _opt(key: str) -> str | None:
        return e.get(key) or None

    return Settings(
        OBS_WS_HOST=_str("OBS_WS_HOST", "127.0.0.1"),
        OBS_WS_PORT=_int("OBS_WS_PORT", 4455),
        OBS_WS_PASSWORD=_str("OBS_WS_PASSWORD", ""),
        OBS_SCENE_NAME=_str("OBS_SCENE_NAME", "RADIO_TAISO_LOOP"),
        OBS_MEDIA_SOURCE_NAME=_opt("OBS_MEDIA_SOURCE_NAME"),
        OBS_PROFILE_NAME=_opt("OBS_PROFILE_NAME"),
        OBS_MEDIA_FILE_PATH=_opt("OBS_MEDIA_FILE_PATH"),
        LOG_DIR=_str("LOG_DIR", "./logs"),
        YOUTUBE_PRIVACY_STATUS=_str("YOUTUBE_PRIVACY_STATUS", "public"),
        YOUTUBE_RESERVATION_BUFFER_MINUTES=_int("YOUTUBE_RESERVATION_BUFFER_MINUTES", 2),
        STREAM_START_TIME=_str("STREAM_START_TIME", "07:00"),
        STREAM_STOP_TIME=_str("STREAM_STOP_TIME", "07:05"),
        ALERT_EMAIL_SENDER=_str("ALERT_EMAIL_SENDER", ""),
        ALERT_EMAIL_PASSWORD=_str("ALERT_EMAIL_PASSWORD", ""),
        ALERT_EMAIL_RECEIVER=_str("ALERT_EMAIL_RECEIVER", ""),
        SMTP_HOST=_str("SMTP_HOST", "smtp.gmail.com"),
        SMTP_PORT=_int("SMTP_PORT", 587),
        DISK_FREE_CRITICAL_GB=_int("DISK_FREE_CRITICAL_GB", 5),
        DISK_FREE_WARN_GB=_int("DISK_FREE_WARN_GB", 20),
    )


# モジュールレベルインスタンス (後方互換)
settings = load_settings()
