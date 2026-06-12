"""subprocess 実行の薄いラッパ (media_probe の ffprobe 実行基盤)。

構築済みコマンド (list[str]) を実行する唯一の入口。テストでは dry_run と
runner 注入で実行を避ける。シェル文字列は使わない。
生成系 (radio-calisthenics-studio) 側には同型の studio/runner.py がある。
"""
from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def format_command(cmd: Sequence[str]) -> str:
    """ログ表示用にコマンドを 1 行へ整形する (実行には使わない)。"""
    return " ".join(shlex.quote(str(c)) for c in cmd)


def run_command(cmd: Sequence[str], *, dry_run: bool = False) -> CommandResult:
    """コマンドを実行して結果を返す。dry_run なら実行せず成功扱い。"""
    if dry_run:
        return CommandResult(returncode=0, stdout="", stderr="")
    proc = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    return CommandResult(returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
