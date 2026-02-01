#!/usr/bin/env python3
"""
健全性監視スクリプト

ラジオ体操配信システムの健全性を監視し、問題があれば通知する。
毎日06:45に実行（配信準備の5分前）。

監視項目:
- launchdタスクのロード状態（3つ全てロード済みか）
- Docker daemon起動状態
- 前日のログから失敗パターン検出
"""
import subprocess
import sys
import os
import glob
from datetime import datetime, timedelta

# プロジェクトルートとsrcディレクトリをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from rct.notify import send_alert_email
from rct.logger import setup_logger

logger = setup_logger()

# 必須のlaunchdタスク
REQUIRED_LAUNCHD_TASKS = [
    "jp.radio-calisthenics-together.prepare",
    "jp.radio-calisthenics-together.start",
    "jp.radio-calisthenics-together.stop",
]

# ログで検出する失敗パターン
FAILURE_PATTERNS = [
    "Timed out waiting for Docker",
    "Connection refused",
    "Failed to connect",
    "Error:",
    "ERROR:",
    "Exception",
    "Traceback",
]


def get_plist_path(task_name):
    """
    タスク名からplistファイルのパスを取得

    Args:
        task_name: launchdタスク名（例: jp.radio-calisthenics-together.start）

    Returns:
        str: plistファイルの絶対パス
    """
    return os.path.expanduser(f"~/Library/LaunchAgents/{task_name}.plist")


def load_launchd_task(task_name):
    """
    launchdタスクをロードする

    Args:
        task_name: ロードするタスク名

    Returns:
        bool: ロード成功ならTrue、失敗ならFalse
    """
    plist_path = get_plist_path(task_name)

    try:
        result = subprocess.run(
            ["launchctl", "load", plist_path],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            logger.info(f"Successfully loaded launchd task: {task_name}")
            return True
        else:
            logger.error(f"Failed to load launchd task {task_name}: {result.stderr}")
            return False
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f"Error loading launchd task {task_name}: {e}")
        return False


def auto_fix_launchd_tasks():
    """
    未ロードのlaunchdタスクを自動的にロードする

    Returns:
        tuple: (修復成功したタスクのリスト, 修復失敗したタスクのリスト)
    """
    missing_tasks = check_launchd_tasks()
    fixed = []
    failed = []

    for task in missing_tasks:
        logger.info(f"Attempting to auto-fix missing launchd task: {task}")
        if load_launchd_task(task):
            fixed.append(task)
        else:
            failed.append(task)

    if fixed:
        logger.info(f"Auto-fixed launchd tasks: {', '.join(fixed)}")
    if failed:
        logger.error(f"Failed to auto-fix launchd tasks: {', '.join(failed)}")

    return fixed, failed


def check_launchd_tasks():
    """
    launchdタスクのロード状態を確認

    Returns:
        list: 未ロードのタスク名リスト（全てロード済みなら空リスト）
    """
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
            check=True
        )
        loaded_tasks = result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to run launchctl list: {e}")
        return REQUIRED_LAUNCHD_TASKS  # エラー時は全て未ロード扱い

    missing_tasks = []
    for task in REQUIRED_LAUNCHD_TASKS:
        if task not in loaded_tasks:
            missing_tasks.append(task)
            logger.warning(f"Launchd task not loaded: {task}")

    return missing_tasks


def check_docker_status():
    """
    Docker daemonの起動状態を確認

    Returns:
        bool: 起動中ならTrue
    """
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning(f"Docker check failed: {e}")
        return False


def check_yesterday_logs():
    """
    前日のログから失敗パターンを検出

    Returns:
        list: 検出された失敗パターンのリスト
    """
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    log_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "logs"
    )

    failures = []

    # ログファイルパターン
    log_patterns = [
        os.path.join(log_dir, f"*{yesterday}*.log"),
        os.path.join(log_dir, "prepare_stdout.log"),
        os.path.join(log_dir, "start_stdout.log"),
        os.path.join(log_dir, "stop_stdout.log"),
    ]

    log_files = []
    for pattern in log_patterns:
        log_files.extend(glob.glob(pattern))

    for log_file in log_files:
        try:
            with open(log_file, 'r') as f:
                content = f.read()

            for pattern in FAILURE_PATTERNS:
                if pattern in content:
                    # 該当行を抽出
                    for line in content.split('\n'):
                        if pattern in line and yesterday in line:
                            failures.append(f"{os.path.basename(log_file)}: {line.strip()}")
                            break
                    else:
                        # 日付が含まれない場合でもパターンマッチを報告
                        if pattern in content:
                            failures.append(f"{os.path.basename(log_file)}: {pattern} found")
        except (IOError, OSError) as e:
            logger.warning(f"Could not read log file {log_file}: {e}")

    return failures


def run_health_check():
    """
    健全性チェックを実行し、問題があれば自動修復を試み、修復できなければ通知

    Returns:
        bool: 全て正常ならTrue、問題ありならFalse
    """
    issues = []

    # 1. launchdタスク確認と自動修復
    missing_tasks = check_launchd_tasks()
    if missing_tasks:
        logger.info(f"Attempting auto-fix for missing launchd tasks: {missing_tasks}")
        fixed, failed = auto_fix_launchd_tasks()
        if failed:
            issues.append(f"自動修復失敗のlaunchdタスク: {', '.join(failed)}")
        if fixed:
            logger.info(f"Auto-fixed launchd tasks: {', '.join(fixed)}")

    # 2. Docker状態確認
    docker_running = check_docker_status()
    if not docker_running:
        issues.append("Dockerが起動していません")

    # 3. 前日ログ確認
    log_failures = check_yesterday_logs()
    if log_failures:
        issues.append(f"前日のログで失敗パターン検出:\n  - " + "\n  - ".join(log_failures))

    # 問題があれば通知
    if issues:
        subject = "健全性チェック警告"
        body = (
            f"Radio Calisthenics Together 健全性チェックで問題を検出しました。\n\n"
            f"検出された問題:\n"
            + "\n".join(f"- {issue}" for issue in issues)
            + f"\n\n時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        logger.warning(f"Health check found issues: {issues}")
        send_alert_email(subject, body)
        return False

    logger.info("Health check passed: All systems operational")
    return True


def main():
    """メイン処理"""
    logger.info("--- Starting Health Monitor ---")

    healthy = run_health_check()

    if healthy:
        logger.info("--- Health Monitor Complete: OK ---")
    else:
        logger.warning("--- Health Monitor Complete: Issues Found ---")
        sys.exit(1)


if __name__ == "__main__":
    main()
