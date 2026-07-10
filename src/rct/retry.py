"""リトライ基盤。

既存 3 箇所の手書きリトライを一元化する:
- start_stream: RetryPolicy.fixed(3, 5)
- youtube_autopost.YouTubeClient token refresh (vendor 内部、独自リトライ実装): 5 回 x 30 秒
- prepare_environment docker: RetryPolicy(intervals=(10, 20))

timing 契約:
- run_with_retry: sleep は試行間のみ (最終試行後に sleep しない)
- poll_until: 失敗ごとに sleep (最終チェック失敗後も sleep — wait_for_docker 互換)
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class RetryPolicy:
    """リトライ設定 (イミュータブル)。

    intervals: 試行間の待機秒数のタプル。長さ = 総試行回数 - 1。
    """
    intervals: tuple[float, ...]

    @classmethod
    def fixed(cls, attempts: int, delay: float) -> "RetryPolicy":
        """N 回試行・均一間隔のポリシーを生成する。"""
        return cls(intervals=tuple(delay for _ in range(attempts - 1)))

    @property
    def total_attempts(self) -> int:
        return len(self.intervals) + 1


def run_with_retry(
    operation: Callable,
    policy: RetryPolicy,
    on_attempt_failure: Optional[Callable[[int, int, Exception], None]] = None,
    sleep: Optional[Callable[[float], None]] = None,
):
    """policy に従って operation をリトライする。

    全試行失敗時は最後の例外を re-raise する。
    on_attempt_failure(attempt_1based, total, exc) は毎失敗後に呼ぶ (ログ seam)。
    sleep 省略時は time.sleep を使う。
    """
    _sleep = sleep if sleep is not None else time.sleep
    total = policy.total_attempts
    last_exc: Optional[Exception] = None

    for idx, _ in enumerate(range(total)):
        try:
            return operation()
        except Exception as exc:
            last_exc = exc
            if on_attempt_failure is not None:
                on_attempt_failure(idx + 1, total, exc)
            if idx < len(policy.intervals):
                _sleep(policy.intervals[idx])

    raise last_exc  # type: ignore[misc]


def poll_until(
    check: Callable[[], bool],
    attempts: int,
    interval: float,
    sleep: Optional[Callable[[float], None]] = None,
) -> bool:
    """check が True を返すまで最大 attempts 回ポーリングする。

    wait_for_docker 互換: チェック失敗のたびに sleep (最終失敗後も sleep)。
    即成功の場合は sleep しない。
    """
    _sleep = sleep if sleep is not None else time.sleep

    for _ in range(attempts):
        if check():
            return True
        _sleep(interval)

    return False
