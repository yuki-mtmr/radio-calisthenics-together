"""Docker Desktop backend の wedge (プロセス生存・応答なし) 検出と自動復旧。

7/7 インシデント: com.docker.backend プロセスが生存したまま応答しなくなり、
timeout なしの `docker info` 呼び出しが orchestrator/prepare/health_monitor/
start/stop/bird を全てハングさせた。flock を握ったまま 3 日間生存し、以降の
全 trigger と verify のリカバリが AlreadyRunning で弾かれ 4 日配信停止した。

設計上の契約:
- wedge 判定は「docker info が連続 timeout」かつ「com.docker.backend プロセスが
  生存」の両方を満たす場合のみ (プロセスが単に起動していないだけのケースと区別)
- 復旧は pkill -9 -f com.docker → open -a Docker → 呼び出し側の wait_ready で確認
- subprocess 呼び出しは全て注入可能 (テストで実プロセスを叩かない)
"""
from __future__ import annotations

import subprocess
import time
from typing import Callable, Optional


def is_backend_process_alive(check_call: Callable = None) -> bool:
    """com.docker.backend プロセスが生存していれば True。"""
    _check_call = check_call if check_call is not None else subprocess.check_call

    try:
        _check_call(
            ["pgrep", "-f", "com.docker.backend"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def force_restart_docker(run: Callable = None) -> None:
    """Docker Desktop backend を強制終了して再起動する。

    pkill -9 で com.docker 系プロセスを一掃してから `open -a Docker` する。
    起動完了の待機は呼び出し側 (wait_ready) の責務。
    """
    _run = run if run is not None else subprocess.run
    _run(["pkill", "-9", "-f", "com.docker"], check=False)
    _run(["open", "-a", "Docker"], check=False)


def check_wedge_and_recover(
    is_ready_detailed: Callable[[], str],
    is_backend_alive: Callable[[], bool],
    restart: Callable[[], None],
    wait_ready: Callable[[], bool],
    consecutive_checks: int = 2,
    check_interval: float = 5.0,
    sleep: Optional[Callable[[float], None]] = None,
) -> str:
    """wedge を判定し、必要なら強制再起動で復旧する。

    Returns:
        'not_wedged'     : wedge ではない (何もしない)
        'recovered'      : wedge を検出し、強制再起動で復旧確認できた
        'recovery_failed': wedge を検出したが、強制再起動後も復旧しなかった

    is_backend_alive() を先に確認する (プロセス自体が無ければ wedge のはずが
    ないので、コストの高い is_ready_detailed の連続ポーリングを省略できる)。
    """
    _sleep = sleep if sleep is not None else time.sleep

    if not is_backend_alive():
        return "not_wedged"

    statuses = []
    for i in range(consecutive_checks):
        statuses.append(is_ready_detailed())
        if i < consecutive_checks - 1:
            _sleep(check_interval)

    if not all(status == "timeout" for status in statuses):
        return "not_wedged"

    restart()
    return "recovered" if wait_ready() else "recovery_failed"
