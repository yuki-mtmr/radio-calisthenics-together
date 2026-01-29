"""
health_monitor.py のテスト

健全性監視スクリプトのテスト。
- launchdタスクのロード状態確認
- Docker daemon起動状態確認
- 前日のログから失敗パターン検出
- 異常検知時にEmail通知
"""
import pytest
from unittest.mock import patch, MagicMock, mock_open
import subprocess
from datetime import datetime, timedelta
import sys
import os

# srcディレクトリとscriptsディレクトリをパスに追加
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(project_root, 'src'))
sys.path.insert(0, os.path.join(project_root, 'scripts'))


class TestCheckLaunchdTasks:
    """check_launchd_tasks 関数のテスト"""

    def test_all_tasks_loaded(self):
        """全てのlaunchdタスクがロード済みの場合、空のリストを返すことをテスト"""
        with patch('health_monitor.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout=(
                    "-\t0\tjp.radio-calisthenics-together.prepare\n"
                    "-\t0\tjp.radio-calisthenics-together.start\n"
                    "-\t0\tjp.radio-calisthenics-together.stop\n"
                ),
                returncode=0
            )

            import health_monitor
            missing = health_monitor.check_launchd_tasks()

            assert missing == []

    def test_one_task_missing(self):
        """1つのlaunchdタスクが未ロードの場合、そのタスク名を返すことをテスト"""
        with patch('health_monitor.subprocess.run') as mock_run:
            # prepareタスクが欠落
            mock_run.return_value = MagicMock(
                stdout=(
                    "-\t0\tjp.radio-calisthenics-together.start\n"
                    "-\t0\tjp.radio-calisthenics-together.stop\n"
                ),
                returncode=0
            )

            import health_monitor
            missing = health_monitor.check_launchd_tasks()

            assert "jp.radio-calisthenics-together.prepare" in missing

    def test_multiple_tasks_missing(self):
        """複数のlaunchdタスクが未ロードの場合、それらのタスク名を返すことをテスト"""
        with patch('health_monitor.subprocess.run') as mock_run:
            # prepareとstartタスクが欠落
            mock_run.return_value = MagicMock(
                stdout="-\t0\tjp.radio-calisthenics-together.stop\n",
                returncode=0
            )

            import health_monitor
            missing = health_monitor.check_launchd_tasks()

            assert "jp.radio-calisthenics-together.prepare" in missing
            assert "jp.radio-calisthenics-together.start" in missing


class TestCheckDockerStatus:
    """check_docker_status 関数のテスト"""

    def test_docker_running(self):
        """Dockerが起動している場合、Trueを返すことをテスト"""
        with patch('health_monitor.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            import health_monitor
            result = health_monitor.check_docker_status()

            assert result is True

    def test_docker_not_running(self):
        """Dockerが起動していない場合、Falseを返すことをテスト"""
        with patch('health_monitor.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            import health_monitor
            result = health_monitor.check_docker_status()

            assert result is False

    def test_docker_command_error(self):
        """dockerコマンドがエラーを返す場合、Falseを返すことをテスト"""
        with patch('health_monitor.subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("docker not found")

            import health_monitor
            result = health_monitor.check_docker_status()

            assert result is False


class TestCheckYesterdayLogs:
    """check_yesterday_logs 関数のテスト"""

    def test_no_failure_pattern(self):
        """ログに失敗パターンがない場合、空のリストを返すことをテスト"""
        with patch('health_monitor.glob.glob') as mock_glob, \
             patch('builtins.open', mock_open(read_data="Stream started successfully")):

            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            mock_glob.return_value = [f"logs/start_{yesterday}.log"]

            import health_monitor
            failures = health_monitor.check_yesterday_logs()

            assert failures == []

    def test_docker_timeout_failure(self):
        """ログにDockerタイムアウトがある場合、それを返すことをテスト"""
        with patch('health_monitor.glob.glob') as mock_glob, \
             patch('builtins.open', mock_open(read_data="Timed out waiting for Docker")):

            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            mock_glob.return_value = [f"logs/prepare_{yesterday}.log"]

            import health_monitor
            failures = health_monitor.check_yesterday_logs()

            assert len(failures) > 0

    def test_connection_refused_failure(self):
        """ログに接続拒否エラーがある場合、それを返すことをテスト"""
        with patch('health_monitor.glob.glob') as mock_glob, \
             patch('builtins.open', mock_open(read_data="Connection refused")):

            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            mock_glob.return_value = [f"logs/start_{yesterday}.log"]

            import health_monitor
            failures = health_monitor.check_yesterday_logs()

            assert len(failures) > 0

    def test_no_logs_found(self):
        """ログファイルが見つからない場合、空のリストを返すことをテスト"""
        with patch('health_monitor.glob.glob') as mock_glob:
            mock_glob.return_value = []

            import health_monitor
            failures = health_monitor.check_yesterday_logs()

            assert failures == []


class TestRunHealthCheck:
    """run_health_check 関数のテスト"""

    def test_all_healthy_no_notification(self):
        """全て正常な場合、通知を送信しないことをテスト"""
        with patch('health_monitor.send_alert_email') as mock_notify, \
             patch('health_monitor.check_yesterday_logs') as mock_logs, \
             patch('health_monitor.check_docker_status') as mock_docker, \
             patch('health_monitor.check_launchd_tasks') as mock_launchd:

            mock_launchd.return_value = []
            mock_docker.return_value = True
            mock_logs.return_value = []

            import health_monitor
            health_monitor.run_health_check()

            mock_notify.assert_not_called()

    def test_missing_launchd_sends_notification(self):
        """launchdタスクが未ロードの場合、通知を送信することをテスト"""
        with patch('health_monitor.send_alert_email') as mock_notify, \
             patch('health_monitor.check_yesterday_logs') as mock_logs, \
             patch('health_monitor.check_docker_status') as mock_docker, \
             patch('health_monitor.check_launchd_tasks') as mock_launchd:

            mock_launchd.return_value = ["jp.radio-calisthenics-together.prepare"]
            mock_docker.return_value = True
            mock_logs.return_value = []

            import health_monitor
            health_monitor.run_health_check()

            mock_notify.assert_called_once()
            call_args = mock_notify.call_args
            # 件名または本文にlaunchdまたはprepareが含まれる
            content = call_args[0][0] + call_args[0][1]
            assert "launchd" in content.lower() or "prepare" in content.lower()

    def test_docker_not_running_sends_notification(self):
        """Dockerが起動していない場合、通知を送信することをテスト"""
        with patch('health_monitor.send_alert_email') as mock_notify, \
             patch('health_monitor.check_yesterday_logs') as mock_logs, \
             patch('health_monitor.check_docker_status') as mock_docker, \
             patch('health_monitor.check_launchd_tasks') as mock_launchd:

            mock_launchd.return_value = []
            mock_docker.return_value = False
            mock_logs.return_value = []

            import health_monitor
            health_monitor.run_health_check()

            mock_notify.assert_called_once()
            call_args = mock_notify.call_args
            content = call_args[0][0] + call_args[0][1]
            assert "Docker" in content

    def test_log_failures_sends_notification(self):
        """ログに失敗パターンがある場合、通知を送信することをテスト"""
        with patch('health_monitor.send_alert_email') as mock_notify, \
             patch('health_monitor.check_yesterday_logs') as mock_logs, \
             patch('health_monitor.check_docker_status') as mock_docker, \
             patch('health_monitor.check_launchd_tasks') as mock_launchd:

            mock_launchd.return_value = []
            mock_docker.return_value = True
            mock_logs.return_value = ["Timed out waiting for Docker"]

            import health_monitor
            health_monitor.run_health_check()

            mock_notify.assert_called_once()

    def test_multiple_issues_single_notification(self):
        """複数の問題がある場合、1つの通知にまとめることをテスト"""
        with patch('health_monitor.send_alert_email') as mock_notify, \
             patch('health_monitor.check_yesterday_logs') as mock_logs, \
             patch('health_monitor.check_docker_status') as mock_docker, \
             patch('health_monitor.check_launchd_tasks') as mock_launchd:

            mock_launchd.return_value = ["jp.radio-calisthenics-together.prepare"]
            mock_docker.return_value = False
            mock_logs.return_value = ["Connection refused"]

            import health_monitor
            health_monitor.run_health_check()

            # 1回だけ通知
            mock_notify.assert_called_once()
            call_args = mock_notify.call_args
            body = call_args[0][1]
            # 全ての問題が本文に含まれる
            assert "launchd" in body.lower() or "prepare" in body.lower()
            assert "Docker" in body
