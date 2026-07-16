#!/usr/bin/env python3
"""
環境準備スクリプト

ラジオ体操配信前にDocker/OBSを起動する。
リトライ機能と失敗時の通知機能を備える。
"""
import socket
import subprocess
import time
import sys
import os
from pathlib import Path

# プロジェクトルートとsrcディレクトリをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from rct.notify import send_alert_email
from rct.lockfile import AlreadyRunning, exclusive_run
from rct.docker_ops import DOCKER_BIN_CANDIDATES as _DOCKER_BIN_CANDIDATES, docker_bin as _docker_bin_impl
from rct.docker_ops import wait_for_docker as _docker_ops_wait
from rct.docker_ops import is_docker_ready_detailed as _docker_ops_is_ready_detailed
from rct.docker_ops import is_docker_ready as _docker_ops_is_ready
from rct.retry import RetryPolicy, run_with_retry
from rct import docker_recovery
from rct.deadline import install_deadline

DEADLINE_SECONDS = 20 * 60  # 7/7 wedge インシデント対策: 20 分でハングを強制終了

# 多重 trigger plist (06:30/06:40/06:50) が同時起動するのを防ぐ
LOCK_PATH = Path(project_root) / ".locks" / "prepare.lock"


# リトライ設定: 間隔は10秒、20秒、30秒
# 実使用は (10, 20) のみ。30 は 3 試行目の後に sleep しない仕様のため dead 値。
RETRY_INTERVALS = [10, 20, 30]

# Docker待機設定
DOCKER_WAIT_RETRIES = 90  # リトライ回数
DOCKER_WAIT_INTERVAL = 2  # 各リトライ間隔（秒）
# 壁時計上限。wedge 中は 1 チェックが docker info timeout (15s) を消費するため、
# 回数上限だけでは 90×17s=1530s に膨張し deadline (1200s) が wedge 復旧より
# 先に発火する (2026-07-17 インシデント)。時間でも必ず打ち切る。
DOCKER_WAIT_MAX_SECONDS = 180

# Docker CLI のフルパス候補。launchd 環境下では PATH に Docker のbinが入って
# いない場合があるため絶対パスでフォールバック。
# 5/1インシデント: prepare/monitor が "docker" コマンド見つからず誤通知
# docker_ops と値を同期するため re-export する (list 型は既存テストが依存)
DOCKER_BIN_CANDIDATES = list(_DOCKER_BIN_CANDIDATES)


def _docker_bin():
    """利用可能な docker バイナリパスを返す。docker_ops に委譲。"""
    return _docker_bin_impl(candidates=tuple(DOCKER_BIN_CANDIDATES))


def log(message):
    """タイムスタンプ付きでメッセージを出力"""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def is_app_running(app_name):
    """
    アプリが起動中か確認

    Args:
        app_name: 確認するアプリ名

    Returns:
        bool: 起動中ならTrue
    """
    try:
        # pgrep returns exit code 0 if process found, 1 if not
        subprocess.check_call(["pgrep", "-x", app_name], stdout=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False


def is_docker_running():
    """
    Dockerデーモンが起動中か確認

    docker infoコマンドで確認する。pgrep -x Dockerは不正確
    （Docker Desktopのプロセス名は「com.docker.backend」等のため）。

    7/7 wedge インシデント対策: timeout なしの check_call は無期限ハングし得るため、
    docker_ops.is_docker_ready (timeout 付き) へ委譲する。

    Returns:
        bool: Dockerが応答可能ならTrue
    """
    return _docker_ops_is_ready(_docker_bin())


def open_app(app_name):
    """
    アプリを起動

    Args:
        app_name: 起動するアプリ名
    """
    log(f"Starting {app_name}...")
    subprocess.run(["open", "-a", app_name], check=True)


def wait_for_docker():
    """Dockerの準備完了を待機。ログ行は FAILURE_PATTERNS grep 契約のため維持。

    Returns:
        bool: 準備完了ならTrue、タイムアウトならFalse
    """
    log("Waiting for Docker to be ready...")
    # ループは docker_ops に委譲。ログ文字列はここに残す (health_monitor.FAILURE_PATTERNS 契約)
    if _docker_ops_wait(
        retries=DOCKER_WAIT_RETRIES,
        interval=DOCKER_WAIT_INTERVAL,
        max_total_seconds=DOCKER_WAIT_MAX_SECONDS,
    ):
        log("Docker is ready.")
        return True
    log("Timed out waiting for Docker.")
    return False


def _attempt_wedge_recovery():
    """A2: 全リトライ失敗後、Docker backend の wedge (プロセス生存・応答なし)
    かどうかを判定し、wedge なら強制再起動で復旧を試みる。

    Returns:
        bool: 復旧できた (呼び出し側は起動成功として扱ってよい) なら True。
              wedge でない、または復旧に失敗した場合は False
              (既存の失敗フローへ継続させる)。
    """
    bin_path = _docker_bin()

    def _is_ready_detailed():
        return _docker_ops_is_ready_detailed(bin_path=bin_path)

    def _wait_ready():
        return _docker_ops_wait(
            retries=DOCKER_WAIT_RETRIES,
            interval=DOCKER_WAIT_INTERVAL,
            bin_path=bin_path,
            max_total_seconds=DOCKER_WAIT_MAX_SECONDS,
        )

    result = docker_recovery.check_wedge_and_recover(
        is_ready_detailed=_is_ready_detailed,
        is_backend_alive=docker_recovery.is_backend_process_alive,
        restart=docker_recovery.force_restart_docker,
        wait_ready=_wait_ready,
    )

    if result == "recovered":
        log("Docker wedge detected. Force restart recovered it.")
        send_alert_email(
            "Docker wedge検出・自動復旧",
            "Docker backend が応答なし (wedge) 状態を検出し、強制再起動して復旧しました。\n\n"
            f"時刻: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return True

    if result == "recovery_failed":
        log("Docker wedge detected but force restart did not recover it.")
        send_alert_email(
            "Docker wedge検出・復旧失敗",
            "Docker backend の wedge (応答なし) 状態を検出し強制再起動しましたが、"
            "復旧できませんでした。手動での確認が必要です。\n\n"
            f"時刻: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return False

    return False


def start_docker_with_retry():
    """Dockerをリトライ付きで起動。retry 基盤 (rct.retry) に委譲。

    intervals=(10, 20) → 3試行。全て失敗時は wedge 復旧を試み、それでも
    ダメなら Email 通知して False を返す。
    ログ文・アラート文・返り値は既存テストにピン済み (変更禁止)。
    """
    if is_docker_running():
        log("Docker is already running.")
        return True

    max_attempts = 3  # RetryPolicy(intervals=(10,20)).total_attempts

    def _try_start():
        open_app("Docker")
        if wait_for_docker():
            log("Docker started successfully.")
            return True
        raise RuntimeError("Docker failed to start")

    def _on_fail(attempt, total, exc):
        if attempt < total:
            interval = RETRY_INTERVALS[attempt - 1]
            log(f"Docker failed to start. Retrying in {interval} seconds...")

    try:
        run_with_retry(_try_start, RetryPolicy(intervals=(10, 20)), on_attempt_failure=_on_fail)
        return True
    except RuntimeError:
        if _attempt_wedge_recovery():
            return True
        log("ERROR: Docker failed to start after all retries.")
        send_alert_email(
            "Docker起動失敗",
            f"Dockerの起動に{max_attempts}回試行しましたが、全て失敗しました。\n"
            "手動での確認が必要です。\n\n"
            f"時刻: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return False


OBS_WS_PORT = 4455
OBS_WS_HOST = "127.0.0.1"
OBS_WS_WAIT_RETRIES = 30
OBS_WS_WAIT_INTERVAL = 2  # 60 秒


def is_obs_websocket_responsive():
    """OBS WebSocket port (4455) に TCP 接続できれば True。

    5/21 インシデント: OBS プロセスは生きていても WebSocket が応答しない状態が
    あった。プロセス存在だけでは判定不十分なため TCP ping で確認する。
    """
    try:
        with socket.create_connection((OBS_WS_HOST, OBS_WS_PORT), timeout=3):
            return True
    except (socket.error, socket.timeout):
        return False


def ensure_obs_running():
    """OBS プロセスと WebSocket の両方が健全であることを保証する。

    プロセスが生きていても WebSocket が応答しない場合は pkill → 再起動。
    """
    if is_app_running("OBS") and is_obs_websocket_responsive():
        log("OBS is healthy (process + WebSocket OK).")
        return

    if is_app_running("OBS"):
        log("OBS process running but WebSocket not responsive. Forcing restart...")
        subprocess.run(["pkill", "-x", "OBS"], check=False)
        time.sleep(3)
    else:
        log("OBS is NOT running.")

    open_app("OBS")

    for _ in range(OBS_WS_WAIT_RETRIES):
        if is_obs_websocket_responsive():
            log("OBS WebSocket is responsive.")
            return
        time.sleep(OBS_WS_WAIT_INTERVAL)
    log(f"WARNING: OBS WebSocket not responsive after {OBS_WS_WAIT_RETRIES * OBS_WS_WAIT_INTERVAL}s.")


def _run_preparation():
    """環境準備の実体 (lock 取得済み前提)"""
    log("--- Checking Environment Pre-flight ---")

    # 1. Docker起動（リトライ付き）
    if not start_docker_with_retry():
        log("Exiting due to Docker failure.")
        sys.exit(1)

    # 2. OBS health check (5/21 インシデント対応: WebSocket 応答まで確認)
    ensure_obs_running()

    log("--- Environment Preparation Complete ---")


def main():
    """multi-trigger guard 付きエントリポイント"""
    install_deadline(DEADLINE_SECONDS, "prepare_environment")
    try:
        with exclusive_run(LOCK_PATH):
            _run_preparation()
    except AlreadyRunning:
        log("Already running (multi-trigger guard), skipping.")
        sys.exit(0)


if __name__ == "__main__":
    main()
