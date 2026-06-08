"""Process-wide exclusive lock for multi-trigger launchd jobs.

複数の launchd plist trigger (例: 06:30/06:40/06:50) で同じスクリプトが
重複起動するのを防ぐ。最初の trigger が lock を取り、後続は AlreadyRunning
を上げて即終了する。
"""
from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class AlreadyRunning(Exception):
    """別プロセスが既に同名 lock を保持している。"""


@contextmanager
def exclusive_run(lock_path: Path) -> Iterator[None]:
    """ファイル lock を非ブロッキングで取得。

    既に lock を保持しているプロセスがあれば AlreadyRunning を上げる。
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise AlreadyRunning(f"Lock held: {lock_path}") from exc
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
