#!/usr/bin/env python3
"""
環境準備スクリプト

ラジオ体操配信前にDocker/OBSを起動する。
リトライ機能と失敗時の通知機能を備える。
"""
import subprocess
import time
import sys
import os

# プロジェクトルートとsrcディレクトリをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from rct.notify import send_alert_email


# リトライ設定: 間隔は10秒、20秒、30秒
RETRY_INTERVALS = [10, 20, 30]

# Docker待機設定
DOCKER_WAIT_RETRIES = 90  # リトライ回数
DOCKER_WAIT_INTERVAL = 2  # 各リトライ間隔（秒）
# 合計タイムアウト: 90回 × 2秒 = 180秒（3分）
# 3回リトライで最大約9分待機可能


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
            ["docker", "info"],
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
                ["docker", "info"],
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


def main():
    """メイン処理"""
    log("--- Checking Environment Pre-flight ---")

    # 1. Docker起動（リトライ付き）
    if not start_docker_with_retry():
        log("Exiting due to Docker failure.")
        sys.exit(1)

    # 2. Check OBS
    if not is_app_running("OBS"):
        log("OBS is NOT running.")
        open_app("OBS")
        # Give OBS a moment to start
        time.sleep(5)
    else:
        log("OBS is already running.")

    log("--- Environment Preparation Complete ---")


if __name__ == "__main__":
    main()
