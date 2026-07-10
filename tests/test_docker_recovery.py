"""rct.docker_recovery の仕様テスト (TDD: 実装より先に作成)。

7/7 インシデント: Docker Desktop backend が wedge (プロセス生存・socket 接続可・
応答なし) し、timeout なしの docker info 呼び出しが全スクリプトをハングさせた。
このモジュールは「wedge の判定」と「強制再起動による復旧」を担う。

設計上の契約:
- 判定は「docker info が連続 timeout」かつ「com.docker.backend プロセスが生存」
- 復旧は pkill -9 -f com.docker → open -a Docker → wait_for_docker
- 全ての subprocess 呼び出しは注入可能 (テストで実プロセスを叩かない)
"""
from unittest.mock import MagicMock, call

import subprocess

from rct import docker_recovery


# --------------------------------------------------- is_backend_process_alive

def test_backend_alive_when_pgrep_succeeds():
    calls = []

    def fake_check_call(cmd, **kwargs):
        calls.append(cmd)
        return 0

    assert docker_recovery.is_backend_process_alive(check_call=fake_check_call) is True
    assert calls == [["pgrep", "-f", "com.docker.backend"]]


def test_backend_not_alive_when_pgrep_fails():
    def fake_check_call(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd)

    assert docker_recovery.is_backend_process_alive(check_call=fake_check_call) is False


def test_backend_not_alive_when_pgrep_missing():
    def fake_check_call(cmd, **kwargs):
        raise FileNotFoundError(cmd[0])

    assert docker_recovery.is_backend_process_alive(check_call=fake_check_call) is False


# ------------------------------------------------------- force_restart_docker

def test_force_restart_kills_then_opens_docker():
    recorded = []

    def fake_run(cmd, **kwargs):
        recorded.append(cmd)

    docker_recovery.force_restart_docker(run=fake_run)

    assert recorded[0] == ["pkill", "-9", "-f", "com.docker"]
    assert recorded[1] == ["open", "-a", "Docker"]


# --------------------------------------------------------- check_wedge_and_recover

def test_not_wedged_when_backend_not_alive():
    """docker info が timeout でも backend プロセスが無ければ wedge ではない
    (例: Docker Desktop がそもそも起動していないだけ)。"""
    is_ready_detailed = MagicMock(return_value="timeout")
    is_backend_alive = MagicMock(return_value=False)
    restart = MagicMock()
    wait_ready = MagicMock()

    result = docker_recovery.check_wedge_and_recover(
        is_ready_detailed=is_ready_detailed,
        is_backend_alive=is_backend_alive,
        restart=restart,
        wait_ready=wait_ready,
        sleep=lambda s: None,
    )

    assert result == "not_wedged"
    restart.assert_not_called()
    wait_ready.assert_not_called()


def test_not_wedged_when_ready_status_is_not_all_timeout():
    """途中で 'ready' や 'error' が混じれば wedge と判定しない (一時的な失敗と区別)。"""
    is_ready_detailed = MagicMock(side_effect=["timeout", "error"])
    is_backend_alive = MagicMock(return_value=True)
    restart = MagicMock()
    wait_ready = MagicMock()

    result = docker_recovery.check_wedge_and_recover(
        is_ready_detailed=is_ready_detailed,
        is_backend_alive=is_backend_alive,
        restart=restart,
        wait_ready=wait_ready,
        sleep=lambda s: None,
    )

    assert result == "not_wedged"
    restart.assert_not_called()


def test_wedge_detected_and_recovered():
    """連続 timeout + backend 生存 → 強制再起動 → wait_ready が True なら recovered。"""
    is_ready_detailed = MagicMock(return_value="timeout")
    is_backend_alive = MagicMock(return_value=True)
    restart = MagicMock()
    wait_ready = MagicMock(return_value=True)
    sleeps = []

    result = docker_recovery.check_wedge_and_recover(
        is_ready_detailed=is_ready_detailed,
        is_backend_alive=is_backend_alive,
        restart=restart,
        wait_ready=wait_ready,
        consecutive_checks=2,
        check_interval=5,
        sleep=sleeps.append,
    )

    assert result == "recovered"
    assert is_ready_detailed.call_count == 2
    restart.assert_called_once()
    wait_ready.assert_called_once()
    assert sleeps == [5]  # チェック間のみ sleep (最終後は不要)


def test_wedge_detected_but_recovery_fails():
    """強制再起動しても wait_ready が False なら recovery_failed。"""
    is_ready_detailed = MagicMock(return_value="timeout")
    is_backend_alive = MagicMock(return_value=True)
    restart = MagicMock()
    wait_ready = MagicMock(return_value=False)

    result = docker_recovery.check_wedge_and_recover(
        is_ready_detailed=is_ready_detailed,
        is_backend_alive=is_backend_alive,
        restart=restart,
        wait_ready=wait_ready,
        sleep=lambda s: None,
    )

    assert result == "recovery_failed"
    restart.assert_called_once()


def test_backend_alive_checked_before_expensive_polling():
    """backend が生存していなければ is_ready_detailed の連続チェックすら行わず即 not_wedged
    (テスト環境で Docker が入っていない場合に高速に抜けるための最適化)。"""
    is_ready_detailed = MagicMock(return_value="timeout")
    is_backend_alive = MagicMock(return_value=False)
    restart = MagicMock()
    wait_ready = MagicMock()

    result = docker_recovery.check_wedge_and_recover(
        is_ready_detailed=is_ready_detailed,
        is_backend_alive=is_backend_alive,
        restart=restart,
        wait_ready=wait_ready,
        sleep=lambda s: None,
    )

    assert result == "not_wedged"
    is_ready_detailed.assert_not_called()
