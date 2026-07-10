#!/usr/bin/env python3
"""start_stream wrapper: Docker daemon retry + compose run.

5/20 インシデント根本原因: launchd の StartCalendarInterval が wake 直後の
DarkWake で 06:50 prepare をスキップ → 06:59 start が Docker daemon 未起動の
状態で `docker compose run` を叩き `Cannot connect to the Docker daemon` で
失敗。

このラッパーは compose run の前に Docker daemon の応答を最大 60 秒待つ。
prepare が遅延しても start 単独で Docker の起動完了を待てる。
"""
import subprocess
import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from rct.lockfile import AlreadyRunning, exclusive_run
from rct.notify import send_alert_email
from rct.docker_ops import wait_for_docker as _docker_ops_wait
from rct.deadline import install_deadline, register_child

DOCKER_BIN = "/Applications/Docker.app/Contents/Resources/bin/docker"
DOCKER_WAIT_RETRIES = 30
DOCKER_WAIT_INTERVAL = 2  # 30 × 2 = 60 秒
LOCK_PATH = project_root / ".locks" / "start_stream.lock"
DEADLINE_SECONDS = 30 * 60  # 7/7 wedge インシデント対策: 30 分でハングを強制終了


def wait_for_docker() -> bool:
    """Docker daemon が `docker info` に応答するまで待機。最大 60 秒。docker_ops に委譲。"""
    return _docker_ops_wait(retries=DOCKER_WAIT_RETRIES, interval=DOCKER_WAIT_INTERVAL, bin_path=DOCKER_BIN)


def main() -> None:
    """orchestrator と既存 start.plist の同時発火を lock で 1 つに収束。

    5/21 インシデント: 2 つの start_stream が並走 → OBS が同時に
    2 つの start_streaming コマンドを受け取りクラッシュ。
    """
    install_deadline(DEADLINE_SECONDS, "start_stream_wrapper")
    try:
        with exclusive_run(LOCK_PATH):
            _run_with_docker()
    except AlreadyRunning:
        print(
            "start_stream_wrapper: already running (multi-trigger guard), skipping.",
            file=sys.stderr,
        )
        sys.exit(0)


def _run_with_docker() -> None:
    if not wait_for_docker():
        msg = (
            f"start_stream_wrapper: Docker daemon did not respond within "
            f"{DOCKER_WAIT_RETRIES * DOCKER_WAIT_INTERVAL}s. "
            f"Aborting before compose run."
        )
        print(msg, file=sys.stderr)
        try:
            send_alert_email("配信開始失敗 (Docker daemon タイムアウト)", msg)
        except Exception as exc:  # noqa: BLE001
            print(f"alert email failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # HIGH: deadline (SIGALRM) は自プロセスしか止められない。start_new_session=True で
    # 子プロセス自身に pgid を持たせ、register_child で deadline に登録することで
    # deadline 発火時に compose run ごと killpg できるようにする。
    proc = subprocess.Popen(
        [
            DOCKER_BIN,
            "compose",
            "run",
            "--rm",
            "rct",
            "python",
            "scripts/start_stream.py",
        ],
        cwd=str(project_root),
        start_new_session=True,
    )
    register_child(proc)
    sys.exit(proc.wait())


if __name__ == "__main__":
    main()
