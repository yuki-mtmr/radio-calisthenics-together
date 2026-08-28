#!/usr/bin/env python3
"""orchestrator: 配信フロー全体を 1 プロセスで順序保証実行。

5/20 インシデント以降の段階 2 対策。launchd の StartCalendarInterval が
wake 直後の DarkWake で取りこぼされても、1 回でも trigger が成立すれば
内部 sleep で prepare → start → stop までを順序保証する。

複数 trigger (06:25/06:30/06:35) を許容するため lock file で多重起動を抑止。
launchd 個別 plist (prepare/start/stop) も併存する二重防衛。
"""
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from rct.lockfile import AlreadyRunning, exclusive_run
from rct.logger import setup_logger
from rct.notify import send_alert_email
from rct.deadline import install_deadline, register_child

logger = setup_logger()

DEADLINE_SECONDS = 100 * 60  # 7/7 wedge インシデント対策 + 子 deadline 予算不足修正:
# 子 deadline 合計 65 分 (prepare 20 + start 30 + stop 15) + 固定時刻 sleep (06:25 起動〜07:05
# 停止で最大 40 分待ち得る) + マージンを賄うため 75 分から 100 分へ引き上げ。
LOCK_PATH = project_root / ".locks" / "orchestrator.lock"
PYTHON_BIN = str(project_root / ".venv" / "bin" / "python3")
PREPARE_SCRIPT = str(project_root / "scripts" / "prepare_environment.py")
START_WRAPPER = str(project_root / "scripts" / "start_stream_wrapper.py")
STOP_WRAPPER = str(project_root / "scripts" / "stop_stream_wrapper.py")

STREAM_START_HOUR = 6
STREAM_START_MINUTE = 59
STREAM_STOP_HOUR = 7
STREAM_STOP_MINUTE = 5
CAFFEINATE_SEC = 3000  # 50 分: 06:25 起動なら 07:15 まで保持


def _today_at(hour: int, minute: int) -> datetime:
    return datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)


def _sleep_until(target_dt: datetime) -> None:
    """target_dt まで sleep。既に過ぎていれば即 return。"""
    wait = (target_dt - datetime.now()).total_seconds()
    if wait > 0:
        logger.info(
            f"orchestrator: sleeping {wait:.0f}s until {target_dt.strftime('%H:%M:%S')}"
        )
        time.sleep(wait)


def _run_subprocess(args: list) -> int:
    """子プロセスを start_new_session=True で起動し、deadline に登録して完了を待つ。

    HIGH: deadline (SIGALRM) は自プロセスしか止められない。docker compose run 等の
    子プロセスは start_new_session=True で自身の pgid を持たせ、rct.deadline に
    登録することで deadline 発火時に killpg でプロセスグループごと殺せるようにする。
    """
    proc = subprocess.Popen(args, start_new_session=True)
    register_child(proc)
    return proc.wait()


def _run_prepare() -> int:
    logger.info("orchestrator: running prepare_environment.py")
    return _run_subprocess([PYTHON_BIN, PREPARE_SCRIPT])


def _run_start() -> None:
    logger.info("orchestrator: running start_stream_wrapper.py")
    _run_subprocess([PYTHON_BIN, START_WRAPPER])


def _run_stop() -> None:
    logger.info("orchestrator: running stop_stream_wrapper.py")
    _run_subprocess([PYTHON_BIN, STOP_WRAPPER])


def _run_full_flow() -> None:
    rc = _run_prepare()
    if rc != 0:
        # prepare はディスク critical 等で exit 1 する (水際ガード)。ここで止めないと
        # 壊れた環境のまま start/stop が走り、翌日枠の予約まで失う (2026-08-06)。
        logger.error(
            "orchestrator: prepare_environment.py failed (rc=%s); "
            "aborting start/stop for today.", rc
        )
        return
    _sleep_until(_today_at(STREAM_START_HOUR, STREAM_START_MINUTE))
    _run_start()
    _sleep_until(_today_at(STREAM_STOP_HOUR, STREAM_STOP_MINUTE))
    _run_stop()
    logger.info("orchestrator: full flow completed.")


def main() -> None:
    install_deadline(DEADLINE_SECONDS, "orchestrator")
    try:
        with exclusive_run(LOCK_PATH):
            logger.info("orchestrator: lock acquired, starting flow")
            caffeinate_proc = subprocess.Popen(
                ["/usr/bin/caffeinate", "-dis", "-t", str(CAFFEINATE_SEC)]
            )
            try:
                _run_full_flow()
            finally:
                caffeinate_proc.terminate()
                try:
                    caffeinate_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    caffeinate_proc.kill()
    except AlreadyRunning:
        logger.info("orchestrator: already running (multi-trigger guard), skipping.")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"orchestrator: unexpected error: {exc}")
        try:
            send_alert_email(
                "Orchestrator failure",
                f"orchestrator crashed: {exc}",
            )
        except Exception as email_exc:  # noqa: BLE001
            logger.error(f"alert email failed: {email_exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
