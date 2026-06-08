"""Tests for rct.lockfile - exclusive run guard for multi-trigger plists."""
import multiprocessing
import time
from pathlib import Path

import pytest

from rct.lockfile import AlreadyRunning, exclusive_run


def _hold_lock(lock_path: str, hold_seconds: float, ready_event) -> None:
    """Child process: hold the lock for `hold_seconds`."""
    from rct.lockfile import exclusive_run

    with exclusive_run(Path(lock_path)):
        ready_event.set()
        time.sleep(hold_seconds)


def test_lock_acquires_and_releases(tmp_path: Path) -> None:
    lock = tmp_path / "test.lock"
    with exclusive_run(lock):
        assert lock.exists()
    with exclusive_run(lock):
        pass


def test_lock_blocks_concurrent_acquisition(tmp_path: Path) -> None:
    lock = tmp_path / "test.lock"
    ready = multiprocessing.Event()
    holder = multiprocessing.Process(target=_hold_lock, args=(str(lock), 2.0, ready))
    holder.start()
    try:
        assert ready.wait(timeout=3.0), "child failed to acquire lock"
        with pytest.raises(AlreadyRunning):
            with exclusive_run(lock):
                pass
    finally:
        holder.join(timeout=5)


def test_lock_creates_parent_directory(tmp_path: Path) -> None:
    lock = tmp_path / "nested" / "dir" / "test.lock"
    with exclusive_run(lock):
        assert lock.parent.is_dir()


def test_lock_released_after_exception(tmp_path: Path) -> None:
    lock = tmp_path / "test.lock"
    with pytest.raises(RuntimeError, match="boom"):
        with exclusive_run(lock):
            raise RuntimeError("boom")
    with exclusive_run(lock):
        pass
