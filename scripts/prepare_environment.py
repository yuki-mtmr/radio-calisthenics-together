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

# 多重 trigger plist (06:30/06:40/06:50) が同時起動するのを防ぐ
LOCK_PATH = Path(project_root) / ".locks" / "prepare.lock"


# リトライ設定: 間隔は10秒、20秒、30秒
RETRY_INTERVALS = [10, 20, 30]

# Docker待機設定
DOCKER_WAIT_RETRIES = 90  # リトライ回数
DOCKER_WAIT_INTERVAL = 2  # 各リトライ間隔（秒）
# 合計タイムアウト: 90回 × 2秒 = 180秒（3分）
# 3回リトライで最大約9分待機可能

# Docker CLI のフルパス候補。launchd 環境下では PATH に Docker のbinが入って
# いない場合があるため絶対パスでフォールバック。
# 5/1インシデント: prepare/monitor が "docker" コマンド見つからず誤通知
DOCKER_BIN_CANDIDATES = [
    "/Applications/Docker.app/Contents/Resources/bin/docker",
    "/usr/local/bin/docker",
    "/opt/homebrew/bin/docker",
    "docker",  # PATH fallback
]


def _docker_bin():
    """利用可能な docker バイナリパスを返す。"""
    for path in DOCKER_BIN_CANDIDATES:
        if path == "docker" or os.path.isfile(path):
            return path
    return "docker"  # 最後のフォールバック


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
    （Docker Desktopのプロセス名は「com.docker.backend」等のため）

    Returns:
        bool: Dockerが応答可能ならTrue
    """
    try:
        subprocess.check_call(
            [_docker_bin(), "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def open_app(app_name):
    """
    アプリを起動

    Args:
        app_name: 起動するアプリ名
    """
    log(f"Starting {app_name}...")
    subprocess.run(["open", "-a", app_name], check=True)


def wait_for_docker():
    """
    Dockerの準備完了を待機

    Returns:
        bool: 準備完了ならTrue、タイムアウトならFalse
    """
    log("Waiting for Docker to be ready...")
    for i in range(DOCKER_WAIT_RETRIES):
        try:
            subprocess.check_call(
                [_docker_bin(), "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            log("Docker is ready.")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            time.sleep(DOCKER_WAIT_INTERVAL)
    log("Timed out waiting for Docker.")
    return False


def start_docker_with_retry():
    """
    Dockerをリトライ付きで起動

    リトライ回数: 3回（間隔: 10秒、20秒、30秒）
    全て失敗した場合、Email通知を送信しFalseを返す。

    Returns:
        bool: Docker起動成功ならTrue、失敗ならFalse
    """
    # 既に起動している場合（docker infoで確認）
    if is_docker_running():
        log("Docker is already running.")
        return True

    # 最大3回試行
    max_attempts = 3
    for attempt in range(max_attempts):
        log(f"Docker startup attempt {attempt + 1}/{max_attempts}")
        open_app("Docker")

        if wait_for_docker():
            log("Docker started successfully.")
            return True

        # 最後の試行でなければ、間隔を空けてリトライ
        if attempt < max_attempts - 1:
            interval = RETRY_INTERVALS[attempt]
            log(f"Docker failed to start. Retrying in {interval} seconds...")
            time.sleep(interval)

    # 全て失敗した場合、通知を送信
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
    try:
        with exclusive_run(LOCK_PATH):
            _run_preparation()
    except AlreadyRunning:
        log("Already running (multi-trigger guard), skipping.")
        sys.exit(0)


if __name__ == "__main__":
    main()
