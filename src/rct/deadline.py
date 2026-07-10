"""プロセス全体の実行時間上限 (deadline) を signal.alarm で強制する。

7/7 インシデントの最終防衛線。docker_ops / docker_recovery の timeout 対策を
すり抜けるあらゆるハング (未知の subprocess, ネットワーク呼び出し等) に対して、
「このスクリプトはどれだけ長くても N 秒で終わる」ことを保証する。

超過時は logger.error → send_alert_email → (任意の on_timeout) → os._exit(1)。
os._exit を使うのは atexit/finally を経由せず即座にプロセスを終了させるため
(中途半端な lock 解放・後処理でさらに時間を消費させない)。
"""
from __future__ import annotations

import os
import signal
import time
from typing import Callable, Optional

from rct.logger import setup_logger
from rct.notify import send_alert_email

logger = setup_logger()

# deadline 発火時に一緒に kill する子プロセス (Popen 互換オブジェクト、.pid を持つ) の登録簿。
# HIGH: SIGALRM は自プロセスしか止められない。docker compose run 等の子プロセスを
# start_new_session=True で起動し、ここに登録しておくことで deadline 発火時に
# プロセスグループごと killpg できるようにする。
_registered_children: list = []


def register_child(proc) -> None:
    """deadline 発火時に killpg 対象とする子プロセスを登録する。

    proc は subprocess.Popen (または .pid を持つ互換オブジェクト)。
    start_new_session=True で起動されている前提 (proc.pid == そのプロセスグループの pgid)。
    """
    _registered_children.append(proc)


def _kill_registered_children(name: str) -> None:
    """登録済みの子プロセスを os.killpg で強制終了する。個別の失敗は握りつぶす。"""
    for proc in list(_registered_children):
        pid = getattr(proc, "pid", None)
        if pid is None:
            continue
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, OSError) as exc:
            logger.error(f"{name}: failed to killpg child pid={pid}: {exc}")


def _make_handler(seconds: int, name: str, on_timeout: Optional[Callable[[], None]]):
    """SIGALRM ハンドラを生成する (signal を使わず直接呼んでテスト可能)。"""

    def _handler(signum, frame):
        logger.error(f"{name}: deadline exceeded ({seconds}s). Forcing exit.")

        _kill_registered_children(name)

        try:
            send_alert_email(
                f"{name} タイムアウト (deadline 超過)",
                f"{name} が {seconds} 秒の deadline を超過したため強制終了しました。\n"
                "ハング状態が疑われます。手動での確認が必要です。\n\n"
                f"時刻: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            )
        except Exception as exc:  # noqa: BLE001 — 最終防衛線なので握りつぶす
            logger.error(f"{name}: alert email failed during deadline handling: {exc}")

        if on_timeout is not None:
            try:
                on_timeout()
            except Exception as exc:  # noqa: BLE001
                logger.error(f"{name}: on_timeout callback failed: {exc}")

        os._exit(1)

    return _handler


def install_deadline(
    seconds: int,
    name: str,
    on_timeout: Optional[Callable[[], None]] = None,
) -> None:
    """seconds 秒後に SIGALRM で強制終了する deadline を仕込む。

    メインスレッドから呼ぶこと (signal.alarm はメインスレッド限定)。
    プロセスが正常に seconds 秒未満で終了すれば alarm は発火しない。

    呼び出しごとに子プロセス登録簿をリセットする (新しいエントリポイントの開始とみなす)。
    """
    _registered_children.clear()
    handler = _make_handler(seconds, name, on_timeout)
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
