"""prepare_environment.py の contract テスト (characterization)。

P3 (docker_ops/retry 委譲) の互換基準となるピン:
- 事故対応で調整済みの定数値 (DO NOT リスト対象)
- health_monitor.FAILURE_PATTERNS が grep するログ文字列
- アラート件名 (完全一致)
- lock ファイルパス規約

既存 test_prepare_environment.py は編集せず新規ファイルで追加する。
"""
import subprocess
from unittest.mock import patch

import prepare_environment


class TestIncidentTunedConstants:
    """凍結定数。値を変えるリファクタは即デグレ扱い。"""

    def test_retry_intervals_value(self):
        """RETRY_INTERVALS は [10, 20, 30]。実使用は (10, 20) のみで 30 は dead
        (3 試行の間の待機は 2 回しか発生しない)。挙動は変えず値を凍結する。
        実際の sleep 列 [10, 20] は test_prepare_environment.py の
        test_docker_retry_intervals がピン済み。"""
        assert prepare_environment.RETRY_INTERVALS == [10, 20, 30]

    def test_docker_wait_settings(self):
        """90 回 × 2 秒 = 180 秒待機 (5/1 インシデント後の調整値)。"""
        assert prepare_environment.DOCKER_WAIT_RETRIES == 90
        assert prepare_environment.DOCKER_WAIT_INTERVAL == 2

    def test_docker_bin_candidates_order(self):
        """launchd 環境の PATH 問題対策の絶対パス候補。順序も契約 (先勝ち)。
        P3 で rct.docker_ops へ移設後も list として re-export されること。"""
        assert prepare_environment.DOCKER_BIN_CANDIDATES == [
            "/Applications/Docker.app/Contents/Resources/bin/docker",
            "/usr/local/bin/docker",
            "/opt/homebrew/bin/docker",
            "docker",
        ]

    def test_obs_websocket_settings(self):
        """5/21 インシデント対応の OBS WebSocket health check 設定。"""
        assert prepare_environment.OBS_WS_PORT == 4455
        assert prepare_environment.OBS_WS_WAIT_RETRIES == 30
        assert prepare_environment.OBS_WS_WAIT_INTERVAL == 2

    def test_lock_path_convention(self):
        """多重 trigger guard の lock パス。.locks/ は host-only 設計。"""
        assert prepare_environment.LOCK_PATH.name == "prepare.lock"
        assert prepare_environment.LOCK_PATH.parent.name == ".locks"


class TestLogStringContracts:
    """health_monitor.FAILURE_PATTERNS / 翌朝観測ゲートが grep する文字列。
    print ベースの log() 出力は capsys で観測する。"""

    def test_wait_for_docker_timeout_log_line(self, capsys):
        with patch("prepare_environment.subprocess.check_call",
                   side_effect=subprocess.CalledProcessError(1, "docker")), \
             patch("prepare_environment.time.sleep"):
            assert prepare_environment.wait_for_docker() is False
        out = capsys.readouterr().out
        assert "Timed out waiting for Docker." in out

    def test_wait_for_docker_ready_log_line(self, capsys):
        with patch("prepare_environment.subprocess.check_call", return_value=0):
            assert prepare_environment.wait_for_docker() is True
        out = capsys.readouterr().out
        assert "Docker is ready." in out

    def test_docker_failure_alert_subject_exact(self):
        """アラート件名は完全一致契約 (受信側のメールフィルタが依存しうる)。"""
        with patch("prepare_environment.send_alert_email") as mock_notify, \
             patch("prepare_environment.wait_for_docker", return_value=False), \
             patch("prepare_environment.open_app"), \
             patch("prepare_environment.is_docker_running", return_value=False), \
             patch("prepare_environment.time.sleep"):
            assert prepare_environment.start_docker_with_retry() is False
        assert mock_notify.call_args[0][0] == "Docker起動失敗"
