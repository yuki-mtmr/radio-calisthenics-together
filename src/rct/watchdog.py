"""Stale プロセス watchdog。

7/7 インシデント: Docker wedge によりハングした prepare_environment.py が
flock を握ったまま 3 日間生存し、以降の全 trigger と verify のリカバリが
AlreadyRunning で弾かれ 4 日配信停止した。「失敗」でなく「永久待機」だった
ためアラートも飛ばなかった。

health_monitor が毎朝、対象スクリプトの経過時間 (`ps` の etime) を確認し、
2 時間を超えていれば強制 kill してアラートする。これは他のヘルスチェックが
ハングしても水際で殺せるよう、run_health_check の最初に実行する契約。
"""
from __future__ import annotations

import os
import re
import signal
import subprocess
from typing import Callable, Optional

TARGET_SCRIPT_NAMES: tuple[str, ...] = (
    "orchestrator.py",
    "prepare_environment.py",
    "start_stream_wrapper.py",
    "stop_stream_wrapper.py",
    "health_monitor.py",
    "bird_director.py",
)

DEFAULT_MAX_AGE_SECONDS = 2 * 60 * 60  # 2 時間


_PYTHON_EXE_RE = re.compile(r"^(?:.*/)?python[0-9.]*$")


def _is_python_invocation(tokens: list[str]) -> bool:
    """command のトークン列に python インタプリタ実行体が含まれるか。

    `less scripts/foo.py` や `grep foo.py x` のような、対象スクリプト名を
    含むだけの無関係プロセスを弾くための判定 (HIGH: watchdog 誤 kill 対策)。
    """
    return any(_PYTHON_EXE_RE.match(tok) for tok in tokens)


def _is_docker_compose_run(tokens: list[str]) -> bool:
    """`docker compose run ... python scripts/<name>.py` 形式か。

    bird_director.py 等は Docker CLI 経由で常駐するため、python 実行体トークンが
    docker compose の子引数として現れる。docker/compose/run が揃っていれば対象とする。
    """
    return "docker" in tokens and "compose" in tokens and "run" in tokens


def _script_arg_matches(tokens: list[str], name: str) -> bool:
    """トークンのいずれかが対象スクリプト名を「引数」として指しているか。

    部分一致ではなくトークン単位の完全一致/パス末尾一致に限定する。
    """
    return any(
        tok == name or tok.endswith("/" + name)
        for tok in tokens
    )


def _matches_target_script(command: str, name: str) -> bool:
    """command が「python (または docker compose run) が対象スクリプトを実行している」
    プロセスかどうかを判定する。command 文字列への裸の部分一致は誤検出の元。
    """
    tokens = command.split()
    if not _script_arg_matches(tokens, name):
        return False
    return _is_python_invocation(tokens) or _is_docker_compose_run(tokens)


def parse_etime(etime: str) -> int:
    """ps の etime 表記 ([[dd-]hh:]mm:ss / ss) を秒数に変換する。"""
    days = 0
    rest = etime
    if "-" in etime:
        days_str, rest = etime.split("-", 1)
        days = int(days_str)

    parts = [int(p) for p in rest.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    hours, minutes, seconds = parts[-3], parts[-2], parts[-1]

    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def find_stale_processes(
    ps_lines: list[str],
    target_names: tuple[str, ...] = TARGET_SCRIPT_NAMES,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    self_pid: Optional[int] = None,
) -> list[dict]:
    """`ps -eo pid=,etime=,command=` 形式の行から stale なプロセスを抽出する。

    フォーマット不正な行は無視する (壊れた ps 出力でクラッシュさせないため)。
    """
    stale = []

    for line in ps_lines:
        line = line.strip()
        if not line:
            continue

        parts = line.split(None, 2)
        if len(parts) < 3:
            continue

        pid_str, etime_str, command = parts

        try:
            pid = int(pid_str)
        except ValueError:
            continue

        if self_pid is not None and pid == self_pid:
            continue

        matched_name = next(
            (name for name in target_names if _matches_target_script(command, name)), None
        )
        if matched_name is None:
            continue

        try:
            age_seconds = parse_etime(etime_str)
        except ValueError:
            continue

        if age_seconds > max_age_seconds:
            stale.append({
                "pid": pid,
                "name": matched_name,
                "age_seconds": age_seconds,
                "command": command,
            })

    return stale


def kill_stale_processes(stale: list[dict], kill_fn: Callable[[int], None] = None) -> list[dict]:
    """stale プロセスを強制終了する。既に死んでいるものは無視する。"""
    _kill = kill_fn if kill_fn is not None else (lambda pid: os.kill(pid, signal.SIGKILL))

    killed = []
    for proc in stale:
        try:
            _kill(proc["pid"])
            killed.append(proc)
        except (ProcessLookupError, OSError):
            continue

    return killed


def _default_get_ps_lines() -> list[str]:
    """実 ps コマンドから対象行を取得する。timeout 付きで自身がハングしない。"""
    result = subprocess.run(
        ["ps", "-eo", "pid=,etime=,command="],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.splitlines()


def run_stale_process_watchdog(
    get_ps_lines: Optional[Callable[[], list[str]]] = None,
    kill_fn: Optional[Callable[[int], None]] = None,
    alert_fn: Optional[Callable[[list[dict]], None]] = None,
    self_pid: Optional[int] = None,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    target_names: tuple[str, ...] = TARGET_SCRIPT_NAMES,
) -> list[dict]:
    """全体フロー: ps 取得 → stale 検出 → kill → (killed があれば) alert。

    Returns:
        list[dict]: 強制終了したプロセスのリスト (空なら何もしなかった)。
    """
    _get_ps_lines = get_ps_lines if get_ps_lines is not None else _default_get_ps_lines

    ps_lines = _get_ps_lines()
    stale = find_stale_processes(
        ps_lines, target_names=target_names, max_age_seconds=max_age_seconds, self_pid=self_pid
    )
    killed = kill_stale_processes(stale, kill_fn=kill_fn)

    if killed and alert_fn is not None:
        alert_fn(killed)

    return killed
