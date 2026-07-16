"""Docker バイナリ解決と readiness 待機の一元化。

prepare_environment.py と health_monitor.py に重複していた 14 行を抽出。

設計上の契約:
- logging は一切しない。"Timed out waiting for Docker" 等のログ文字列は
  health_monitor.FAILURE_PATTERNS が grep する runtime 契約のため、
  ログは呼び出し側 (prepare_environment 等) に残す
- subprocess 呼び出しは check_call / is_ready 注入で差し替え可能
"""
from __future__ import annotations

import subprocess
import time
from typing import Callable, Optional

DOCKER_BIN_CANDIDATES: tuple[str, ...] = (
    "/Applications/Docker.app/Contents/Resources/bin/docker",
    "/usr/local/bin/docker",
    "/opt/homebrew/bin/docker",
    "docker",  # PATH fallback
)


def docker_bin(
    candidates: tuple[str, ...] = DOCKER_BIN_CANDIDATES,
    exists: Callable[[str], bool] = None,
) -> str:
    """利用可能な docker バイナリパスを返す。

    "docker" は PATH fallback のためファイル存在チェックをしない。
    """
    import os
    _exists = exists if exists is not None else os.path.isfile

    for path in candidates:
        if path == "docker" or _exists(path):
            return path
    return "docker"


DEFAULT_READY_TIMEOUT = 15  # 秒。7/7 wedge インシデント対策 (無期限 check_call 禁止)


def is_docker_ready_detailed(
    bin_path: str,
    check_call: Callable = None,
    timeout: float = DEFAULT_READY_TIMEOUT,
) -> str:
    """docker info の結果を 'ready' | 'error' | 'timeout' で区別して返す。

    timeout は wedge (プロセス生存・応答なし) 検出の土台。呼び出し側が
    'timeout' を他の失敗と区別できることで docker_recovery の wedge 判定に使える。
    """
    _check_call = check_call if check_call is not None else subprocess.check_call

    try:
        _check_call(
            [bin_path, "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
        return "ready"
    except subprocess.TimeoutExpired:
        return "timeout"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "error"


def is_docker_ready(
    bin_path: str,
    check_call: Callable = None,
    timeout: float = DEFAULT_READY_TIMEOUT,
) -> bool:
    """docker info が成功すれば True。CalledProcessError / FileNotFoundError / TimeoutExpired は False。"""
    return (
        is_docker_ready_detailed(bin_path, check_call=check_call, timeout=timeout)
        == "ready"
    )


def wait_for_docker(
    retries: int,
    interval: float,
    is_ready: Optional[Callable[[], bool]] = None,
    sleep: Optional[Callable[[float], None]] = None,
    bin_path: Optional[str] = None,
    max_total_seconds: Optional[float] = None,
    monotonic: Optional[Callable[[], float]] = None,
) -> bool:
    """is_ready が True を返すまで retries 回ポーリングする。

    wait_for_docker 互換タイミング:
    - 即成功 → sleep なし
    - 失敗ごとに sleep (最終チェック失敗後も sleep)

    max_total_seconds は壁時計時間の上限。wedge 中は is_ready 1 回が
    subprocess timeout (15s) を消費するため、回数上限だけでは
    retries × (timeout + interval) まで膨張し deadline を先に踏む
    (2026-07-17 インシデント)。上限超過時は残り回数を捨てて False を返す。

    is_ready 省略時は is_docker_ready(docker_bin()) を使う。
    sleep 省略時は time.sleep、monotonic 省略時は time.monotonic を使う。
    """
    _sleep = sleep if sleep is not None else time.sleep
    _monotonic = monotonic if monotonic is not None else time.monotonic

    if is_ready is None:
        _bin = bin_path if bin_path is not None else docker_bin()
        _is_ready = lambda: is_docker_ready(_bin)
    else:
        _is_ready = is_ready

    start = _monotonic()
    for _ in range(retries):
        if _is_ready():
            return True
        if (
            max_total_seconds is not None
            and _monotonic() - start >= max_total_seconds
        ):
            return False
        _sleep(interval)

    return False
