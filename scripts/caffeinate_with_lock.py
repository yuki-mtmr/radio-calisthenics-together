#!/usr/bin/env python3
"""caffeinate wrapper with multi-trigger lock.

複数の launchd plist trigger (06:30/06:40/06:48) が呼ばれる前提で、
最初の 1 回だけ /usr/bin/caffeinate を 22 分起動する。
後続 trigger は lock を取れず即終了する。
"""
import os
import subprocess
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from rct.lockfile import AlreadyRunning, exclusive_run

LOCK_PATH = project_root / ".locks" / "caffeinate.lock"
CAFFEINATE_DURATION_SEC = 1320  # 22 分: 06:48 起動 → 07:10 まで保持相当


def main() -> None:
    try:
        with exclusive_run(LOCK_PATH):
            subprocess.run(
                ["/usr/bin/caffeinate", "-dis", "-t", str(CAFFEINATE_DURATION_SEC)],
                check=False,
            )
    except AlreadyRunning:
        sys.exit(0)


if __name__ == "__main__":
    main()
