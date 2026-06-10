"""rct.retry の仕様テスト (TDD: 実装より先に作成)。

既存 3 箇所の手書きリトライの挙動を完全互換で抽象化する:
- start_stream: 3 回試行・間隔 5 秒        → RetryPolicy.fixed(3, 5)
- youtube_client token refresh: 5 回・30 秒 → RetryPolicy.fixed(5, 30)
- prepare_environment docker: 間隔 (10, 20) → RetryPolicy(intervals=(10, 20))

重要な timing 互換:
- sleep は「失敗した試行の間」のみ。最終試行の後には sleep しない
- poll_until は既存 wait_for_docker と同一: 失敗チェックの度に sleep
  (最終チェック失敗後も sleep する。90 回 × 2 秒 = 180 秒の実測互換)
"""
import pytest

from rct.retry import RetryPolicy, poll_until, run_with_retry


class _Recorder:
    """sleep 呼び出しを記録する fake。実 time.sleep は呼ばない。"""

    def __init__(self):
        self.calls = []

    def __call__(self, seconds):
        self.calls.append(seconds)


# ---------------------------------------------------------------- RetryPolicy

def test_fixed_policy_intervals():
    """fixed(attempts=N, delay=D) は N-1 個の待機間隔を持つ。"""
    assert RetryPolicy.fixed(3, 5).intervals == (5, 5)
    assert RetryPolicy.fixed(5, 30).intervals == (30, 30, 30, 30)


def test_fixed_policy_single_attempt_has_no_intervals():
    assert RetryPolicy.fixed(1, 10).intervals == ()


def test_policy_total_attempts():
    """総試行回数 = len(intervals) + 1。"""
    assert RetryPolicy(intervals=(10, 20)).total_attempts == 3
    assert RetryPolicy.fixed(5, 30).total_attempts == 5


def test_policy_is_immutable():
    policy = RetryPolicy.fixed(3, 5)
    with pytest.raises(Exception):
        policy.intervals = (1,)


# -------------------------------------------------------------- run_with_retry

def test_success_first_attempt_no_sleep():
    sleep = _Recorder()
    result = run_with_retry(lambda: "ok", RetryPolicy.fixed(3, 5), sleep=sleep)
    assert result == "ok"
    assert sleep.calls == []


def test_success_after_failures_sleeps_between_attempts():
    sleep = _Recorder()
    attempts = []

    def op():
        attempts.append(1)
        if len(attempts) < 3:
            raise ValueError(f"fail {len(attempts)}")
        return "recovered"

    result = run_with_retry(op, RetryPolicy(intervals=(10, 20)), sleep=sleep)
    assert result == "recovered"
    assert len(attempts) == 3
    assert sleep.calls == [10, 20]


def test_all_attempts_fail_reraises_last_exception():
    sleep = _Recorder()
    attempts = []

    def op():
        attempts.append(1)
        raise ValueError(f"fail {len(attempts)}")

    with pytest.raises(ValueError, match="fail 3"):
        run_with_retry(op, RetryPolicy.fixed(3, 5), sleep=sleep)
    assert len(attempts) == 3
    # 最終試行の後には sleep しない
    assert sleep.calls == [5, 5]


def test_on_attempt_failure_callback_receives_context():
    """callback は (attempt 1-based, total, exception) を受け取る。
    呼び出し側が既存のログ文字列 (契約) を維持するための seam。"""
    sleep = _Recorder()
    seen = []

    def op():
        raise ValueError("boom")

    def on_fail(attempt, total, exc):
        seen.append((attempt, total, str(exc)))

    with pytest.raises(ValueError):
        run_with_retry(
            op, RetryPolicy.fixed(3, 1), on_attempt_failure=on_fail, sleep=sleep
        )
    assert seen == [(1, 3, "boom"), (2, 3, "boom"), (3, 3, "boom")]


def test_exception_type_is_not_swallowed():
    class CustomError(RuntimeError):
        pass

    with pytest.raises(CustomError):
        run_with_retry(
            lambda: (_ for _ in ()).throw(CustomError("x")),
            RetryPolicy.fixed(2, 1),
            sleep=_Recorder(),
        )


# ------------------------------------------------------------------ poll_until

def test_poll_immediately_true_no_sleep():
    sleep = _Recorder()
    assert poll_until(lambda: True, attempts=90, interval=2, sleep=sleep) is True
    assert sleep.calls == []


def test_poll_true_on_third_check():
    sleep = _Recorder()
    state = {"n": 0}

    def check():
        state["n"] += 1
        return state["n"] >= 3

    assert poll_until(check, attempts=90, interval=2, sleep=sleep) is True
    assert state["n"] == 3
    # 失敗 2 回分のみ sleep
    assert sleep.calls == [2, 2]


def test_poll_exhausted_returns_false_sleeping_every_failure():
    """既存 wait_for_docker 互換: 最終チェック失敗後も sleep する。"""
    sleep = _Recorder()
    assert poll_until(lambda: False, attempts=5, interval=2, sleep=sleep) is False
    assert sleep.calls == [2, 2, 2, 2, 2]
