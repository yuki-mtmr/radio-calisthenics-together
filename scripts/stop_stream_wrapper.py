#!/usr/bin/env python3
"""stop_stream wrapper: lock + compose run。

5/21 インシデント根本原因: orchestrator と既存 stop.plist が 07:05 に同時発火し
stop_stream.py が 2 つの Docker container で並走、翌日枠を race condition で
2 つ作成。docker-compose の volume mount に `.locks/` が含まれないため、
コンテナ内で lock を取っても共有できない → ホスト側 wrapper で lock を取る。
"""
import subprocess
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from rct.lockfile import AlreadyRunning, exclusive_run
from rct.deadline import install_deadline, register_child

DOCKER_BIN = "/Applications/Docker.app/Contents/Resources/bin/docker"
LOCK_PATH = project_root / ".locks" / "stop_stream.lock"
DEADLINE_SECONDS = 15 * 60  # 7/7 wedge インシデント対策: 15 分でハングを強制終了


def main() -> None:
    install_deadline(DEADLINE_SECONDS, "stop_stream_wrapper")
    try:
        with exclusive_run(LOCK_PATH):
            # HIGH: deadline (SIGALRM) は自プロセスしか止められない。start_new_session=True
            # で子プロセス自身に pgid を持たせ、register_child で登録することで
            # deadline 発火時に compose run ごと killpg できるようにする。
            proc = subprocess.Popen(
                [
                    DOCKER_BIN,
                    "compose",
                    "run",
                    "--rm",
                    "rct",
                    "python",
                    "scripts/stop_stream.py",
                ],
                cwd=str(project_root),
                start_new_session=True,
            )
            register_child(proc)
            sys.exit(proc.wait())
    except AlreadyRunning:
        print(
            "stop_stream_wrapper: already running (multi-trigger guard), skipping.",
            file=sys.stderr,
        )
        sys.exit(0)


if __name__ == "__main__":
    main()
