#!/usr/bin/env python3
"""verify_stream: 配信されているか確認、無ければ自動 retry。

5/20 インシデント以降の最終防衛線。07:01 に launchd で発火し、
YouTube API で「みんなでラジオ体操」の active broadcast を確認する。
存在しなければ start_stream_wrapper を呼んで救済を試みる。
"""
import subprocess
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from rct.logger import setup_logger
from rct.notify import send_alert_email
from rct.youtube_client import YouTubeClient

logger = setup_logger()

TARGET_TITLE_PREFIX = "みんなでラジオ体操"
PYTHON_BIN = str(project_root / ".venv" / "bin" / "python3")
WRAPPER_SCRIPT = str(project_root / "scripts" / "start_stream_wrapper.py")


def is_broadcasting() -> bool:
    yt = YouTubeClient()
    active = yt.list_active_broadcasts()
    for item in active:
        title = item.get("snippet", {}).get("title", "")
        if TARGET_TITLE_PREFIX in title:
            return True
    return False


def main() -> None:
    try:
        broadcasting = is_broadcasting()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"verify_stream: YouTube API check failed: {exc}")
        try:
            send_alert_email(
                "配信検証 API エラー",
                f"verify_stream で YouTube API 呼び出しが失敗しました。\n\n{exc}",
            )
        except Exception as email_exc:  # noqa: BLE001
            logger.error(f"alert email failed: {email_exc}")
        sys.exit(1)

    if broadcasting:
        logger.info("verify_stream: active broadcast found. OK.")
        return

    logger.warning("verify_stream: NOT broadcasting. Triggering recovery.")
    subprocess.run([PYTHON_BIN, WRAPPER_SCRIPT], check=False)


if __name__ == "__main__":
    main()
