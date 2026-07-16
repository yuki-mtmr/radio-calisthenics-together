"""rct.docker_ops の仕様テスト (TDD: 実装より先に作成)。

prepare_environment.py / health_monitor.py に 14 行重複していた
Docker バイナリ解決と readiness 待機を一元化する。

設計上の契約:
- docker_ops は logging を一切しない。"Timed out waiting for Docker" 等の
  ログ文字列は health_monitor.FAILURE_PATTERNS が grep する runtime 契約のため
  呼び出し側 (prepare_environment 等) に残る
- subprocess 呼び出しは check_call 注入で差し替え可能 (テストで実プロセスを叩かない)
"""
import subprocess

from rct.docker_ops import (
    DOCKER_BIN_CANDIDATES,
    docker_bin,
    is_docker_ready,
    is_docker_ready_detailed,
    wait_for_docker,
)


class _Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, seconds):
        self.calls.append(seconds)


# ------------------------------------------------------------------ docker_bin

def test_candidates_match_incident_hardened_list():
    """5/1 インシデント由来の候補リスト (launchd 環境で PATH に docker が無い対策)。"""
    assert DOCKER_BIN_CANDIDATES == (
        "/Applications/Docker.app/Contents/Resources/bin/docker",
        "/usr/local/bin/docker",
        "/opt/homebrew/bin/docker",
        "docker",
    )


def test_docker_bin_returns_first_existing_file(tmp_path):
    real = tmp_path / "docker"
    real.write_text("#!/bin/sh\n")
    assert docker_bin(candidates=(str(tmp_path / "missing"), str(real))) == str(real)


def test_docker_bin_bare_name_accepted_without_file_check():
    """候補 "docker" はファイル存在チェックなしで採用 (PATH fallback)。"""
    assert docker_bin(candidates=("docker", "/nonexistent/docker")) == "docker"


def test_docker_bin_falls_back_to_bare_docker(tmp_path):
    assert docker_bin(candidates=(str(tmp_path / "a"), str(tmp_path / "b"))) == "docker"


# -------------------------------------------------------------- is_docker_ready

def test_ready_when_docker_info_succeeds():
    calls = []

    def fake_check_call(cmd, **kwargs):
        calls.append(cmd)
        return 0

    assert is_docker_ready(bin_path="/fake/docker", check_call=fake_check_call) is True
    assert calls == [["/fake/docker", "info"]]


def test_not_ready_on_called_process_error():
    def fake_check_call(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd)

    assert is_docker_ready(bin_path="/fake/docker", check_call=fake_check_call) is False


def test_not_ready_on_file_not_found():
    def fake_check_call(cmd, **kwargs):
        raise FileNotFoundError(cmd[0])

    assert is_docker_ready(bin_path="/fake/docker", check_call=fake_check_call) is False


def test_not_ready_on_timeout():
    """A1: subprocess.TimeoutExpired は False 扱い (ハング根絶)。"""
    def fake_check_call(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))

    assert is_docker_ready(bin_path="/fake/docker", check_call=fake_check_call) is False


def test_default_timeout_is_15_seconds_and_forwarded():
    calls = []

    def fake_check_call(cmd, **kwargs):
        calls.append(kwargs.get("timeout"))
        return 0

    is_docker_ready(bin_path="/fake/docker", check_call=fake_check_call)
    assert calls == [15]


def test_custom_timeout_is_forwarded():
    calls = []

    def fake_check_call(cmd, **kwargs):
        calls.append(kwargs.get("timeout"))
        return 0

    is_docker_ready(bin_path="/fake/docker", check_call=fake_check_call, timeout=5)
    assert calls == [5]


# ----------------------------------------------------- is_docker_ready_detailed

def test_detailed_ready():
    assert (
        is_docker_ready_detailed(bin_path="/fake/docker", check_call=lambda cmd, **kw: 0)
        == "ready"
    )


def test_detailed_error_on_called_process_error():
    def fake_check_call(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd)

    assert (
        is_docker_ready_detailed(bin_path="/fake/docker", check_call=fake_check_call)
        == "error"
    )


def test_detailed_error_on_file_not_found():
    def fake_check_call(cmd, **kwargs):
        raise FileNotFoundError(cmd[0])

    assert (
        is_docker_ready_detailed(bin_path="/fake/docker", check_call=fake_check_call)
        == "error"
    )


def test_detailed_timeout():
    """呼び出し側が timeout と error/成功を区別できることを担保する (wedge 検出の土台)。"""
    def fake_check_call(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))

    assert (
        is_docker_ready_detailed(bin_path="/fake/docker", check_call=fake_check_call)
        == "timeout"
    )


# -------------------------------------------------------------- wait_for_docker

def test_wait_returns_true_immediately_when_ready():
    sleep = _Recorder()
    assert (
        wait_for_docker(retries=90, interval=2, is_ready=lambda: True, sleep=sleep)
        is True
    )
    assert sleep.calls == []


def test_wait_polls_until_ready():
    sleep = _Recorder()
    state = {"n": 0}

    def fake_ready():
        state["n"] += 1
        return state["n"] >= 4

    assert (
        wait_for_docker(retries=90, interval=2, is_ready=fake_ready, sleep=sleep)
        is True
    )
    assert state["n"] == 4
    assert sleep.calls == [2, 2, 2]


def test_wait_timeout_matches_legacy_timing():
    """既存実装互換: retries 回失敗 → False、sleep は毎失敗後 (retries 回)。"""
    sleep = _Recorder()
    assert (
        wait_for_docker(retries=5, interval=2, is_ready=lambda: False, sleep=sleep)
        is False
    )
    assert sleep.calls == [2, 2, 2, 2, 2]


def test_wait_stops_when_wall_clock_budget_exceeded():
    """7/17 インシデント対策: wedge 中は 1 チェックが 15s timeout を消費するため、
    回数上限 (90回) だけでは 1530s かかり deadline (1200s) を先に踏む。
    max_total_seconds を渡すと壁時計時間で打ち切る。"""
    sleep = _Recorder()
    clock = {"t": 0.0}

    def slow_not_ready():
        clock["t"] += 17.0  # docker info timeout 15s + interval 2s 相当
        return False

    result = wait_for_docker(
        retries=90,
        interval=2,
        is_ready=slow_not_ready,
        sleep=sleep,
        max_total_seconds=180,
        monotonic=lambda: clock["t"],
    )
    assert result is False
    # 180s 到達で打ち切り (17s/チェック → 11 回目で 187s >= 180)
    assert len(sleep.calls) <= 11


def test_wait_budget_none_keeps_legacy_behavior():
    """max_total_seconds 未指定なら従来どおり retries 回数で制御。"""
    sleep = _Recorder()
    assert (
        wait_for_docker(
            retries=5, interval=2, is_ready=lambda: False, sleep=sleep,
            monotonic=lambda: 0.0,
        )
        is False
    )
    assert sleep.calls == [2, 2, 2, 2, 2]
