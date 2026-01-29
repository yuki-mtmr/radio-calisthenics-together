"""
prepare_environment.py のテスト

Docker起動リトライロジックと通知機能のテスト。
"""
import pytest
from unittest.mock import patch, MagicMock, call
import subprocess
import sys
import os

# srcディレクトリとscriptsディレクトリをパスに追加
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(project_root, 'src'))
sys.path.insert(0, os.path.join(project_root, 'scripts'))


class TestIsAppRunning:
    """is_app_running 関数のテスト"""

    def test_app_running_returns_true(self):
        """アプリが起動中の場合、Trueを返すことをテスト"""
        with patch('subprocess.check_call') as mock_check_call:
            # 新規インポートでパッチが適用されるようにする
            import importlib
            import prepare_environment
            importlib.reload(prepare_environment)

            mock_check_call.return_value = 0

            result = prepare_environment.is_app_running("OBS")

            assert result is True

    def test_app_not_running_returns_false(self):
        """アプリが起動していない場合、Falseを返すことをテスト"""
        with patch('subprocess.check_call') as mock_check_call:
            import importlib
            import prepare_environment
            importlib.reload(prepare_environment)

            mock_check_call.side_effect = subprocess.CalledProcessError(1, "pgrep")

            result = prepare_environment.is_app_running("OBS")

            assert result is False


class TestIsDockerRunning:
    """is_docker_running 関数のテスト（Docker専用のチェック）"""

    def test_docker_running_when_docker_info_succeeds(self):
        """docker infoが成功する場合、Trueを返すことをテスト"""
        with patch('subprocess.check_call') as mock_check_call:
            import importlib
            import prepare_environment
            importlib.reload(prepare_environment)

            mock_check_call.return_value = 0

            result = prepare_environment.is_docker_running()

            assert result is True
            # docker infoコマンドが呼ばれていることを確認
            mock_check_call.assert_called_once()
            call_args = mock_check_call.call_args[0][0]
            assert call_args == ["docker", "info"]

    def test_docker_not_running_when_docker_info_fails(self):
        """docker infoが失敗する場合、Falseを返すことをテスト"""
        with patch('subprocess.check_call') as mock_check_call:
            import importlib
            import prepare_environment
            importlib.reload(prepare_environment)

            mock_check_call.side_effect = subprocess.CalledProcessError(1, "docker")

            result = prepare_environment.is_docker_running()

            assert result is False

    def test_docker_not_running_when_docker_not_found(self):
        """dockerコマンドが見つからない場合、Falseを返すことをテスト"""
        with patch('subprocess.check_call') as mock_check_call:
            import importlib
            import prepare_environment
            importlib.reload(prepare_environment)

            mock_check_call.side_effect = FileNotFoundError()

            result = prepare_environment.is_docker_running()

            assert result is False


class TestOpenApp:
    """open_app 関数のテスト"""

    def test_open_app_calls_open_command(self):
        """アプリを起動するopen -aコマンドが呼ばれることをテスト"""
        with patch('subprocess.run') as mock_run:
            import importlib
            import prepare_environment
            importlib.reload(prepare_environment)

            prepare_environment.open_app("Docker")

            mock_run.assert_called_once_with(["open", "-a", "Docker"], check=True)


class TestWaitForDocker:
    """wait_for_docker 関数のテスト"""

    def test_wait_for_docker_success_immediately(self):
        """Dockerがすぐに応答する場合、Trueを返すことをテスト"""
        with patch('subprocess.check_call') as mock_check_call, \
             patch('time.sleep') as mock_sleep:
            import importlib
            import prepare_environment
            importlib.reload(prepare_environment)

            mock_check_call.return_value = 0

            result = prepare_environment.wait_for_docker()

            assert result is True
            mock_sleep.assert_not_called()

    def test_wait_for_docker_success_after_retries(self):
        """数回リトライ後にDockerが応答する場合、Trueを返すことをテスト"""
        with patch('subprocess.check_call') as mock_check_call, \
             patch('time.sleep') as mock_sleep:
            import importlib
            import prepare_environment
            importlib.reload(prepare_environment)

            # 最初の2回は失敗、3回目で成功
            mock_check_call.side_effect = [
                subprocess.CalledProcessError(1, "docker"),
                subprocess.CalledProcessError(1, "docker"),
                0
            ]

            result = prepare_environment.wait_for_docker()

            assert result is True
            assert mock_sleep.call_count == 2

    def test_wait_for_docker_timeout(self):
        """タイムアウトした場合、Falseを返すことをテスト"""
        with patch('subprocess.check_call') as mock_check_call, \
             patch('time.sleep') as mock_sleep:
            import importlib
            import prepare_environment
            importlib.reload(prepare_environment)

            mock_check_call.side_effect = subprocess.CalledProcessError(1, "docker")

            result = prepare_environment.wait_for_docker()

            assert result is False


class TestStartDockerWithRetry:
    """start_docker_with_retry 関数のテスト（新規追加機能）"""

    def test_docker_already_running(self):
        """Dockerが既に起動している場合、起動処理をスキップしTrueを返すことをテスト"""
        with patch('prepare_environment.send_alert_email') as mock_notify, \
             patch('prepare_environment.wait_for_docker') as mock_wait, \
             patch('prepare_environment.open_app') as mock_open, \
             patch('prepare_environment.is_docker_running') as mock_is_docker, \
             patch('time.sleep') as mock_sleep:

            mock_is_docker.return_value = True

            import prepare_environment
            result = prepare_environment.start_docker_with_retry()

            assert result is True
            mock_open.assert_not_called()
            mock_wait.assert_not_called()
            mock_notify.assert_not_called()

    def test_docker_starts_first_try(self):
        """Dockerが最初の試行で起動した場合、Trueを返すことをテスト"""
        with patch('prepare_environment.send_alert_email') as mock_notify, \
             patch('prepare_environment.wait_for_docker') as mock_wait, \
             patch('prepare_environment.open_app') as mock_open, \
             patch('prepare_environment.is_docker_running') as mock_is_docker, \
             patch('time.sleep') as mock_sleep:

            mock_is_docker.return_value = False
            mock_wait.return_value = True

            import prepare_environment
            result = prepare_environment.start_docker_with_retry()

            assert result is True
            mock_open.assert_called_once_with("Docker")
            mock_notify.assert_not_called()

    def test_docker_starts_after_retry(self):
        """Dockerがリトライ後に起動した場合、Trueを返すことをテスト"""
        with patch('prepare_environment.send_alert_email') as mock_notify, \
             patch('prepare_environment.wait_for_docker') as mock_wait, \
             patch('prepare_environment.open_app') as mock_open, \
             patch('prepare_environment.is_docker_running') as mock_is_docker, \
             patch('time.sleep') as mock_sleep:

            mock_is_docker.return_value = False
            # 1回目失敗、2回目成功
            mock_wait.side_effect = [False, True]

            import prepare_environment
            result = prepare_environment.start_docker_with_retry()

            assert result is True
            assert mock_open.call_count == 2
            mock_notify.assert_not_called()
            # 10秒待機（最初のリトライ間隔）
            mock_sleep.assert_called_with(10)

    def test_docker_fails_all_retries_sends_notification(self):
        """全てのリトライが失敗した場合、通知を送信しFalseを返すことをテスト"""
        with patch('prepare_environment.send_alert_email') as mock_notify, \
             patch('prepare_environment.wait_for_docker') as mock_wait, \
             patch('prepare_environment.open_app') as mock_open, \
             patch('prepare_environment.is_docker_running') as mock_is_docker, \
             patch('time.sleep') as mock_sleep:

            mock_is_docker.return_value = False
            mock_wait.return_value = False

            import prepare_environment
            result = prepare_environment.start_docker_with_retry()

            assert result is False
            # 3回試行
            assert mock_open.call_count == 3
            # 通知が送信される
            mock_notify.assert_called_once()
            call_args = mock_notify.call_args
            assert "Docker" in call_args[0][0]  # 件名にDockerが含まれる

    def test_docker_retry_intervals(self):
        """リトライ間隔が10秒、20秒であることをテスト"""
        with patch('prepare_environment.send_alert_email') as mock_notify, \
             patch('prepare_environment.wait_for_docker') as mock_wait, \
             patch('prepare_environment.open_app') as mock_open, \
             patch('prepare_environment.is_docker_running') as mock_is_docker, \
             patch('time.sleep') as mock_sleep:

            mock_is_docker.return_value = False
            mock_wait.return_value = False

            import prepare_environment
            prepare_environment.start_docker_with_retry()

            # リトライ間隔を確認（10秒、20秒のみ。3回目の後は待機しない）
            sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
            assert sleep_calls == [10, 20]


class TestMain:
    """main 関数のテスト"""

    def test_main_exits_on_docker_failure(self):
        """Docker起動失敗時にsys.exit(1)で終了することをテスト"""
        with patch('prepare_environment.sys.exit') as mock_exit, \
             patch('prepare_environment.start_docker_with_retry') as mock_docker_retry, \
             patch('prepare_environment.open_app') as mock_open, \
             patch('prepare_environment.is_app_running') as mock_is_running, \
             patch('time.sleep') as mock_sleep:

            mock_docker_retry.return_value = False

            import prepare_environment
            prepare_environment.main()

            mock_exit.assert_called_once_with(1)

    def test_main_continues_when_docker_succeeds(self):
        """Docker起動成功時にOBS起動処理に進むことをテスト"""
        with patch('prepare_environment.sys.exit') as mock_exit, \
             patch('prepare_environment.start_docker_with_retry') as mock_docker_retry, \
             patch('prepare_environment.open_app') as mock_open, \
             patch('prepare_environment.is_app_running') as mock_is_running, \
             patch('time.sleep') as mock_sleep:

            mock_docker_retry.return_value = True
            mock_is_running.return_value = False  # OBSは起動していない

            import prepare_environment
            prepare_environment.main()

            mock_exit.assert_not_called()
            mock_open.assert_called_with("OBS")
