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


from rct.disk import OK_LEVEL, DiskStatus
_DISK_OK = DiskStatus(OK_LEVEL, 100.0, "空き 100.0GB (ok)")


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
            # docker infoコマンドが呼ばれていることを確認（絶対パス対応）
            mock_check_call.assert_called_once()
            call_args = mock_check_call.call_args[0][0]
            assert call_args[-1] == "info"
            assert call_args[0].endswith("docker")

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

    def test_docker_not_running_on_timeout(self):
        """docker info がタイムアウトした場合、Falseを返すことをテスト（7/7 wedge対策）。

        timeout なしの check_call は無期限ハングし得るため、docker_ops.is_docker_ready
        (timeout 付き) への委譲を検証する。
        """
        with patch('subprocess.check_call') as mock_check_call:
            import importlib
            import prepare_environment
            importlib.reload(prepare_environment)

            mock_check_call.side_effect = subprocess.TimeoutExpired(cmd="docker", timeout=15)

            result = prepare_environment.is_docker_running()

            assert result is False

    def test_is_docker_running_delegates_to_docker_ops_is_ready(self):
        """is_docker_running が docker_ops.is_docker_ready (timeout 付き) に委譲する。"""
        import importlib
        import prepare_environment
        importlib.reload(prepare_environment)

        with patch('prepare_environment._docker_ops_is_ready') as mock_is_ready, \
             patch('prepare_environment._docker_bin', return_value="/resolved/docker"):
            mock_is_ready.return_value = True

            result = prepare_environment.is_docker_running()

            assert result is True
            mock_is_ready.assert_called_once_with("/resolved/docker")


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

    def test_wait_for_docker_timeout_is_180_seconds(self):
        """タイムアウトが180秒（90回 × 2秒）であることをテスト"""
        with patch('subprocess.check_call') as mock_check_call, \
             patch('time.sleep') as mock_sleep:
            import importlib
            import prepare_environment
            importlib.reload(prepare_environment)

            # Dockerが常に失敗するようにモック
            mock_check_call.side_effect = subprocess.CalledProcessError(1, "docker")

            result = prepare_environment.wait_for_docker()

            assert result is False
            # リトライ回数が90回であることを確認（180秒タイムアウト）
            # sleep(2)が90回呼ばれる = 180秒
            assert mock_sleep.call_count == 90
            # 各sleepが2秒であることを確認
            for call_item in mock_sleep.call_args_list:
                assert call_item[0][0] == 2


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
             patch('prepare_environment.docker_recovery.check_wedge_and_recover',
                   return_value='not_wedged'), \
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
             patch('prepare_environment.docker_recovery.check_wedge_and_recover',
                   return_value='not_wedged'), \
             patch('time.sleep') as mock_sleep:

            mock_is_docker.return_value = False
            mock_wait.return_value = False

            import prepare_environment
            prepare_environment.start_docker_with_retry()

            # リトライ間隔を確認（10秒、20秒のみ。3回目の後は待機しない）
            sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
            assert sleep_calls == [10, 20]


class TestDockerWedgeRecovery:
    """A2: 7/7 wedge インシデント対策。全リトライ失敗後の wedge 自動復旧。"""

    def test_recovery_success_short_circuits_failure_alert(self):
        """wedge 検出・復旧成功なら Docker起動失敗 通知は送らず True を返す
        (代わりに wedge 復旧を知らせる別件名のアラートを送る)。"""
        with patch('prepare_environment.send_alert_email') as mock_notify, \
             patch('prepare_environment.wait_for_docker') as mock_wait, \
             patch('prepare_environment.open_app') as mock_open, \
             patch('prepare_environment.is_docker_running') as mock_is_docker, \
             patch('prepare_environment.docker_recovery.check_wedge_and_recover',
                   return_value='recovered') as mock_check, \
             patch('time.sleep'):

            mock_is_docker.return_value = False
            mock_wait.return_value = False

            import prepare_environment
            result = prepare_environment.start_docker_with_retry()

            assert result is True
            mock_check.assert_called_once()
            mock_notify.assert_called_once()
            assert mock_notify.call_args[0][0] != "Docker起動失敗"

    def test_recovery_failed_still_sends_original_failure_alert(self):
        """wedge 検出したが復旧失敗 → 既存の Docker起動失敗 アラートは維持 (契約凍結)。"""
        with patch('prepare_environment.send_alert_email') as mock_notify, \
             patch('prepare_environment.wait_for_docker') as mock_wait, \
             patch('prepare_environment.open_app') as mock_open, \
             patch('prepare_environment.is_docker_running') as mock_is_docker, \
             patch('prepare_environment.docker_recovery.check_wedge_and_recover',
                   return_value='recovery_failed') as mock_check, \
             patch('time.sleep'):

            mock_is_docker.return_value = False
            mock_wait.return_value = False

            import prepare_environment
            result = prepare_environment.start_docker_with_retry()

            assert result is False
            mock_check.assert_called_once()
            # 最後に呼ばれた通知は既存契約の件名 (2 回目の呼び出しが最新)
            assert mock_notify.call_args[0][0] == "Docker起動失敗"

    def test_not_wedged_behaves_like_before(self):
        """wedge でなければ既存の失敗フローのみ (通知 1 回)。"""
        with patch('prepare_environment.send_alert_email') as mock_notify, \
             patch('prepare_environment.wait_for_docker') as mock_wait, \
             patch('prepare_environment.open_app') as mock_open, \
             patch('prepare_environment.is_docker_running') as mock_is_docker, \
             patch('prepare_environment.docker_recovery.check_wedge_and_recover',
                   return_value='not_wedged') as mock_check, \
             patch('time.sleep'):

            mock_is_docker.return_value = False
            mock_wait.return_value = False

            import prepare_environment
            result = prepare_environment.start_docker_with_retry()

            assert result is False
            mock_check.assert_called_once()
            mock_notify.assert_called_once()
            assert mock_notify.call_args[0][0] == "Docker起動失敗"


class TestDockerWaitWallClockBound:
    """7/17 インシデント: wedge 中の docker info timeout (15s/回) により
    wait_for_docker が回数上限だけでは 1530s かかり、deadline (1200s) が
    wedge 復旧より先に発火した。壁時計上限 180s を必ず渡す契約。"""

    def test_wait_for_docker_passes_wall_clock_budget(self):
        with patch('prepare_environment._docker_ops_wait', return_value=True) as mock_wait:
            import prepare_environment
            assert prepare_environment.wait_for_docker() is True
            assert mock_wait.call_args.kwargs['max_total_seconds'] == \
                prepare_environment.DOCKER_WAIT_MAX_SECONDS == 180

    def test_wedge_wait_ready_passes_wall_clock_budget(self):
        captured = {}

        def fake_check(**kwargs):
            captured.update(kwargs)
            return 'not_wedged'

        with patch('prepare_environment.docker_recovery.check_wedge_and_recover',
                   side_effect=fake_check), \
             patch('prepare_environment._docker_ops_wait', return_value=True) as mock_wait:
            import prepare_environment
            prepare_environment._attempt_wedge_recovery()
            captured['wait_ready']()
            assert mock_wait.call_args.kwargs['max_total_seconds'] == 180


class TestMain:
    """main 関数のテスト"""

    def test_main_exits_on_docker_failure(self):
        """Docker起動失敗時にsys.exit(1)で終了することをテスト"""
        with patch('prepare_environment.sys.exit') as mock_exit, \
             patch('prepare_environment.check_free_space', return_value=_DISK_OK), \
             patch('prepare_environment.start_docker_with_retry', return_value=False), \
             patch('prepare_environment.ensure_obs_running') as mock_ensure_obs:
            import prepare_environment
            prepare_environment.main()
            mock_exit.assert_called_once_with(1)

    def test_main_continues_when_docker_succeeds(self):
        """Docker起動成功時にOBS起動処理 (ensure_obs_running) に進むことをテスト"""
        with patch('prepare_environment.sys.exit') as mock_exit, \
             patch('prepare_environment.check_free_space', return_value=_DISK_OK), \
             patch('prepare_environment.start_docker_with_retry', return_value=True), \
             patch('prepare_environment.ensure_obs_running') as mock_ensure_obs:
            import prepare_environment
            prepare_environment.main()
            mock_exit.assert_not_called()
            mock_ensure_obs.assert_called_once()


class TestObsHealthCheck:
    """5/21 OBS クラッシュ回帰: プロセスが生きていても WebSocket が死ぬケース"""

    def test_websocket_responsive_returns_true_when_socket_connects(self):
        import importlib
        import prepare_environment
        importlib.reload(prepare_environment)

        with patch("prepare_environment.socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__.return_value = MagicMock()
            mock_conn.return_value.__exit__.return_value = False
            assert prepare_environment.is_obs_websocket_responsive() is True

    def test_websocket_responsive_returns_false_on_connection_refused(self):
        import socket as socket_mod
        import importlib
        import prepare_environment
        importlib.reload(prepare_environment)

        with patch("prepare_environment.socket.create_connection",
                   side_effect=socket_mod.error()):
            assert prepare_environment.is_obs_websocket_responsive() is False

    def test_ensure_obs_running_noop_when_healthy(self):
        """OBS プロセス + WebSocket 共に OK なら何もしない"""
        import importlib
        import prepare_environment
        importlib.reload(prepare_environment)

        with patch("prepare_environment.is_app_running", return_value=True), \
             patch("prepare_environment.is_obs_websocket_responsive", return_value=True), \
             patch("prepare_environment.subprocess.run") as mock_run, \
             patch("prepare_environment.open_app") as mock_open:
            prepare_environment.ensure_obs_running()
            mock_open.assert_not_called()
            mock_run.assert_not_called()

    def test_ensure_obs_running_kills_and_restarts_when_websocket_dead(self):
        """プロセスは生きてるが WebSocket 死亡 → pkill → 再起動 → 復活確認"""
        import importlib
        import prepare_environment
        importlib.reload(prepare_environment)

        with patch("prepare_environment.is_app_running", return_value=True), \
             patch("prepare_environment.is_obs_websocket_responsive",
                   side_effect=[False, True]), \
             patch("prepare_environment.subprocess.run") as mock_run, \
             patch("prepare_environment.open_app") as mock_open, \
             patch("prepare_environment.time.sleep"):
            prepare_environment.ensure_obs_running()

            kill_call = mock_run.call_args_list[0][0][0]
            assert kill_call[0] == "pkill"
            assert "OBS" in kill_call
            mock_open.assert_called_with("OBS")

    def test_ensure_obs_running_starts_when_process_missing(self):
        """OBS プロセスが無ければ起動 → WebSocket 待機"""
        import importlib
        import prepare_environment
        importlib.reload(prepare_environment)

        with patch("prepare_environment.is_app_running", return_value=False), \
             patch("prepare_environment.is_obs_websocket_responsive",
                   side_effect=[False, True]), \
             patch("prepare_environment.subprocess.run") as mock_run, \
             patch("prepare_environment.open_app") as mock_open, \
             patch("prepare_environment.time.sleep"):
            prepare_environment.ensure_obs_running()

            mock_open.assert_called_with("OBS")
            mock_run.assert_not_called()


class TestDeadlineWiring:
    """A3: 7/7 wedge インシデント対策。20分でハングを強制終了する deadline。"""

    def test_main_installs_20_minute_deadline(self):
        import prepare_environment

        with patch('prepare_environment.install_deadline') as mock_install, \
             patch('prepare_environment._run_preparation'), \
             patch('prepare_environment.exclusive_run') as mock_lock:
            mock_lock.return_value.__enter__.return_value = None
            mock_lock.return_value.__exit__.return_value = False

            prepare_environment.main()

            mock_install.assert_called_once_with(20 * 60, "prepare_environment")


class TestExclusiveRunGuard:
    """多重 trigger 抑止のテスト (06:30/06:40/06:50)"""

    def test_main_skips_when_already_running(self, tmp_path):
        """別 trigger が既に動いていれば exit 0 で skip"""
        from rct.lockfile import AlreadyRunning

        import prepare_environment

        with patch('prepare_environment._run_preparation') as mock_run, \
             patch('prepare_environment.exclusive_run') as mock_lock:
            mock_lock.return_value.__enter__.side_effect = AlreadyRunning("locked")
            mock_lock.return_value.__exit__.return_value = False

            with pytest.raises(SystemExit) as exc_info:
                prepare_environment.main()

            assert exc_info.value.code == 0
            mock_run.assert_not_called()

    def test_main_runs_preparation_when_lock_available(self):
        """lock が取れれば通常の準備処理が走る"""
        import prepare_environment

        with patch('prepare_environment._run_preparation') as mock_run, \
             patch('prepare_environment.exclusive_run') as mock_lock:
            mock_lock.return_value.__enter__.return_value = None
            mock_lock.return_value.__exit__.return_value = False

            prepare_environment.main()

            mock_run.assert_called_once()


class TestDiskSpacePreflight:
    """2026-08-06 ENOSPC 事故: 検知しても止めなかったことの直接の修正。

    health_monitor は 06:45 にディスク満杯を検知したがアラートのみで、
    その後 start/verify/stop が全滅した。prepare は Docker 起動より前に
    空き容量を見て、critical なら中断する。
    """

    def test_aborts_before_docker_when_disk_is_critical(self):
        from rct.disk import CRITICAL_LEVEL, DiskStatus

        with patch('prepare_environment.sys.exit', side_effect=SystemExit) as mock_exit, \
             patch('prepare_environment.send_alert_email') as mock_alert, \
             patch('prepare_environment.start_docker_with_retry') as mock_docker, \
             patch('prepare_environment.ensure_obs_running') as mock_obs, \
             patch('prepare_environment.check_free_space') as mock_disk:
            mock_disk.return_value = DiskStatus(
                CRITICAL_LEVEL, 0.2, "空き 0.2GB (critical)"
            )

            import prepare_environment
            with pytest.raises(SystemExit):
                prepare_environment.main()

            mock_exit.assert_called_once_with(1)
            mock_docker.assert_not_called()
            mock_obs.assert_not_called()
            mock_alert.assert_called_once()

    def test_warn_level_does_not_abort(self):
        """warn では配信を落とさない (誤爆で自動配信を殺さない)。"""
        from rct.disk import WARN_LEVEL, DiskStatus

        with patch('prepare_environment.sys.exit') as mock_exit, \
             patch('prepare_environment.check_free_space', return_value=_DISK_OK), \
             patch('prepare_environment.send_alert_email'), \
             patch('prepare_environment.start_docker_with_retry', return_value=True) as mock_docker, \
             patch('prepare_environment.ensure_obs_running') as mock_obs, \
             patch('prepare_environment.check_free_space') as mock_disk:
            mock_disk.return_value = DiskStatus(WARN_LEVEL, 12.0, "空き 12.0GB (warn)")

            import prepare_environment
            prepare_environment.main()

            mock_exit.assert_not_called()
            mock_docker.assert_called_once()
            mock_obs.assert_called_once()

    def test_ok_level_proceeds_without_alert(self):
        from rct.disk import OK_LEVEL, DiskStatus

        with patch('prepare_environment.sys.exit') as mock_exit, \
             patch('prepare_environment.check_free_space', return_value=_DISK_OK), \
             patch('prepare_environment.send_alert_email') as mock_alert, \
             patch('prepare_environment.start_docker_with_retry', return_value=True), \
             patch('prepare_environment.ensure_obs_running'), \
             patch('prepare_environment.check_free_space') as mock_disk:
            mock_disk.return_value = DiskStatus(OK_LEVEL, 103.0, "空き 103.0GB")

            import prepare_environment
            prepare_environment.main()

            mock_exit.assert_not_called()
            mock_alert.assert_not_called()
