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
        """launchdタスクが未ロードで自動修復も失敗した場合、通知を送信することをテスト"""
        with patch('health_monitor.send_alert_email') as mock_notify, \
             patch('health_monitor.check_yesterday_logs') as mock_logs, \
             patch('health_monitor.check_docker_status') as mock_docker, \
             patch('health_monitor.check_launchd_tasks') as mock_launchd, \
             patch('health_monitor.auto_fix_launchd_tasks') as mock_fix:

            mock_launchd.return_value = ["jp.radio-calisthenics-together.prepare"]
            mock_fix.return_value = ([], ["jp.radio-calisthenics-together.prepare"])  # 修復失敗
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
             patch('health_monitor.check_launchd_tasks') as mock_launchd, \
             patch('health_monitor.auto_fix_launchd_tasks') as mock_fix:

            mock_launchd.return_value = ["jp.radio-calisthenics-together.prepare"]
            mock_fix.return_value = ([], ["jp.radio-calisthenics-together.prepare"])  # 修復失敗
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


class TestLoadLaunchdTask:
    """load_launchd_task 関数のテスト"""

    def test_load_task_success(self):
        """launchdタスクのロードに成功した場合、Trueを返すことをテスト"""
        with patch('health_monitor.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            import health_monitor
            result = health_monitor.load_launchd_task("jp.radio-calisthenics-together.start")

            assert result is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "launchctl" in call_args
            assert "load" in call_args

    def test_load_task_failure(self):
        """launchdタスクのロードに失敗した場合、Falseを返すことをテスト"""
        with patch('health_monitor.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            import health_monitor
            result = health_monitor.load_launchd_task("jp.radio-calisthenics-together.start")

            assert result is False

    def test_load_task_file_not_found(self):
        """plistファイルが存在しない場合、Falseを返すことをテスト"""
        with patch('health_monitor.subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "launchctl")

            import health_monitor
            result = health_monitor.load_launchd_task("jp.radio-calisthenics-together.nonexistent")

            assert result is False


class TestAutoFixLaunchdTasks:
    """auto_fix_launchd_tasks 関数のテスト"""

    def test_auto_fix_loads_missing_tasks(self):
        """未ロードのタスクを自動的にロードすることをテスト"""
        with patch('health_monitor.check_launchd_tasks') as mock_check, \
             patch('health_monitor.load_launchd_task') as mock_load:

            mock_check.return_value = ["jp.radio-calisthenics-together.start"]
            mock_load.return_value = True

            import health_monitor
            fixed, failed = health_monitor.auto_fix_launchd_tasks()

            assert "jp.radio-calisthenics-together.start" in fixed
            assert len(failed) == 0
            mock_load.assert_called_once_with("jp.radio-calisthenics-together.start")

    def test_auto_fix_reports_failures(self):
        """ロードに失敗したタスクを報告することをテスト"""
        with patch('health_monitor.check_launchd_tasks') as mock_check, \
             patch('health_monitor.load_launchd_task') as mock_load:

            mock_check.return_value = ["jp.radio-calisthenics-together.start"]
            mock_load.return_value = False

            import health_monitor
            fixed, failed = health_monitor.auto_fix_launchd_tasks()

            assert len(fixed) == 0
            assert "jp.radio-calisthenics-together.start" in failed

    def test_auto_fix_no_missing_tasks(self):
        """全てロード済みの場合、何もしないことをテスト"""
        with patch('health_monitor.check_launchd_tasks') as mock_check, \
             patch('health_monitor.load_launchd_task') as mock_load:

            mock_check.return_value = []

            import health_monitor
            fixed, failed = health_monitor.auto_fix_launchd_tasks()

            assert len(fixed) == 0
            assert len(failed) == 0
            mock_load.assert_not_called()

    def test_auto_fix_multiple_tasks(self):
        """複数の未ロードタスクを全てロードすることをテスト"""
        with patch('health_monitor.check_launchd_tasks') as mock_check, \
             patch('health_monitor.load_launchd_task') as mock_load:

            mock_check.return_value = [
                "jp.radio-calisthenics-together.start",
                "jp.radio-calisthenics-together.stop"
            ]
            mock_load.return_value = True

            import health_monitor
            fixed, failed = health_monitor.auto_fix_launchd_tasks()

            assert len(fixed) == 2
            assert len(failed) == 0
            assert mock_load.call_count == 2


class TestRunHealthCheckWithAutoFix:
    """run_health_check の自動修復機能のテスト"""

    def test_auto_fix_before_notification(self):
        """通知前に自動修復を試みることをテスト"""
        with patch('health_monitor.send_alert_email') as mock_notify, \
             patch('health_monitor.check_yesterday_logs') as mock_logs, \
             patch('health_monitor.check_docker_status') as mock_docker, \
             patch('health_monitor.check_launchd_tasks') as mock_check, \
             patch('health_monitor.auto_fix_launchd_tasks') as mock_fix:

            # 最初は未ロード、修復後はOK
            mock_check.return_value = ["jp.radio-calisthenics-together.start"]
            mock_fix.return_value = (["jp.radio-calisthenics-together.start"], [])
            mock_docker.return_value = True
            mock_logs.return_value = []

            import health_monitor
            health_monitor.run_health_check()

            # 自動修復が呼ばれる
            mock_fix.assert_called_once()

    def test_no_notification_if_auto_fix_succeeds(self):
        """自動修復が成功した場合、通知しないことをテスト"""
        with patch('health_monitor.send_alert_email') as mock_notify, \
             patch('health_monitor.check_yesterday_logs') as mock_logs, \
             patch('health_monitor.check_docker_status') as mock_docker, \
             patch('health_monitor.check_launchd_tasks') as mock_check, \
             patch('health_monitor.auto_fix_launchd_tasks') as mock_fix:

            mock_check.return_value = ["jp.radio-calisthenics-together.start"]
            mock_fix.return_value = (["jp.radio-calisthenics-together.start"], [])
            mock_docker.return_value = True
            mock_logs.return_value = []

            import health_monitor
            result = health_monitor.run_health_check()

            # 通知は送信されない（自動修復成功）
            mock_notify.assert_not_called()
            assert result is True

    def test_notification_if_auto_fix_fails(self):
        """自動修復が失敗した場合、通知することをテスト"""
        with patch('health_monitor.send_alert_email') as mock_notify, \
             patch('health_monitor.check_yesterday_logs') as mock_logs, \
             patch('health_monitor.check_docker_status') as mock_docker, \
             patch('health_monitor.check_launchd_tasks') as mock_check, \
             patch('health_monitor.auto_fix_launchd_tasks') as mock_fix:

            mock_check.return_value = ["jp.radio-calisthenics-together.start"]
            mock_fix.return_value = ([], ["jp.radio-calisthenics-together.start"])
            mock_docker.return_value = True
            mock_logs.return_value = []

            import health_monitor
            result = health_monitor.run_health_check()

            # 通知が送信される（自動修復失敗）
            mock_notify.assert_called_once()
            assert result is False
