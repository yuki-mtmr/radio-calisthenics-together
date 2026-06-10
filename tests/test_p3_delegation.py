"""P3 委譲確認テスト — 既存テストは無編集のまま、委譲が正しく起きていることを検証する。

extract-and-delegate 方式の保証:
- 公開名は全て元のモジュールに残る (patch 文字列 ×20 を温存)
- 中身だけ rct.docker_ops / rct.retry に委譲する
"""
from unittest.mock import MagicMock, patch
import subprocess


# ---------------------------------------------------------------- health_monitor


def test_health_monitor_has_no_standalone_docker_bin_candidates():
    """health_monitor が独自に DOCKER_BIN_CANDIDATES を定義せず docker_ops 経由を使う。

    リファクタ前は lines 145-150 でローカル定義していた (docker_ops と 2 重管理)。
    """
    import importlib
    import health_monitor
    importlib.reload(health_monitor)

    from rct.docker_ops import DOCKER_BIN_CANDIDATES as ops_candidates
    # health_monitor.DOCKER_BIN_CANDIDATES は docker_ops と同一オブジェクトか同値である
    assert tuple(health_monitor.DOCKER_BIN_CANDIDATES) == ops_candidates


def test_health_monitor_check_docker_status_uses_docker_ops_bin():
    """check_docker_status が docker_ops.docker_bin() で解決したパスを使う。"""
    import importlib
    import health_monitor
    importlib.reload(health_monitor)

    calls = []

    def fake_check_call(cmd, **kwargs):
        calls.append(cmd)
        return 0

    with patch("rct.docker_ops.subprocess.check_call", side_effect=fake_check_call), \
         patch("health_monitor.subprocess.run") as mock_run:
        # check_docker_status は subprocess.run を使うが、bin 解決は docker_ops を経由する
        mock_run.return_value = MagicMock(returncode=0)
        result = health_monitor.check_docker_status()

    assert result is True
    # docker info コマンドが呼ばれ、末尾が "info"
    called_cmd = mock_run.call_args[0][0]
    assert called_cmd[-1] == "info"
    assert called_cmd[0].endswith("docker")


# ---------------------------------------------------------- prepare_environment


def test_prepare_environment_docker_bin_candidates_synced_with_docker_ops():
    """prepare_environment.DOCKER_BIN_CANDIDATES が docker_ops と値一致する。"""
    import importlib
    import prepare_environment
    importlib.reload(prepare_environment)

    from rct.docker_ops import DOCKER_BIN_CANDIDATES as ops_candidates
    assert tuple(prepare_environment.DOCKER_BIN_CANDIDATES) == ops_candidates


def test_prepare_wait_for_docker_delegates_to_docker_ops():
    """prepare_environment.wait_for_docker が _docker_ops_wait (docker_ops) に委譲する。

    ループ実装が prepare_environment に残ってはいけない。
    ログ行 ('Waiting for Docker...' など) は呼び出し側に残してよい。
    `from rct.docker_ops import wait_for_docker as _docker_ops_wait` で local 参照なので
    patch 先は prepare_environment._docker_ops_wait。
    """
    import importlib
    import prepare_environment
    importlib.reload(prepare_environment)

    with patch("prepare_environment._docker_ops_wait") as mock_ops_wait:
        mock_ops_wait.return_value = True
        result = prepare_environment.wait_for_docker()

    assert result is True
    mock_ops_wait.assert_called_once()
    # retries=90, interval=2 が渡されている
    kw = mock_ops_wait.call_args[1]
    assert kw.get("retries") == 90
    assert kw.get("interval") == 2


def test_prepare_start_docker_with_retry_uses_rct_retry():
    """start_docker_with_retry が rct.retry.run_with_retry を経由してリトライする。

    intervals=(10, 20) の RetryPolicy で動作する。
    prepare_environment は `from rct.retry import run_with_retry` するため
    patch 先は prepare_environment.run_with_retry。
    """
    import importlib
    import prepare_environment
    importlib.reload(prepare_environment)

    with patch("prepare_environment.run_with_retry") as mock_retry, \
         patch("prepare_environment.is_docker_running", return_value=False), \
         patch("prepare_environment.send_alert_email"):
        from rct.retry import RetryPolicy
        mock_retry.return_value = True

        prepare_environment.start_docker_with_retry()

    mock_retry.assert_called_once()
    policy_arg = mock_retry.call_args[0][1]
    assert isinstance(policy_arg, RetryPolicy)
    assert policy_arg.intervals == (10, 20)


# ------------------------------------------------------ start_stream_wrapper


def test_start_stream_wrapper_wait_for_docker_delegates_to_docker_ops():
    """start_stream_wrapper.wait_for_docker がループを直接持たず docker_ops に委譲する。

    `from rct.docker_ops import wait_for_docker as _docker_ops_wait` なので
    patch 先は start_stream_wrapper._docker_ops_wait。
    """
    import importlib
    import start_stream_wrapper
    importlib.reload(start_stream_wrapper)

    with patch("start_stream_wrapper._docker_ops_wait") as mock_ops_wait:
        mock_ops_wait.return_value = True
        result = start_stream_wrapper.wait_for_docker()

    assert result is True
    mock_ops_wait.assert_called_once()


def test_start_stream_wrapper_compose_array_unchanged():
    """compose-run 引数配列はバイト一致で維持される。

    start_stream_wrapper のテストがこの配列を assert するため凍結。
    """
    import importlib
    import start_stream_wrapper
    importlib.reload(start_stream_wrapper)

    expected_bin = "/Applications/Docker.app/Contents/Resources/bin/docker"
    with patch("start_stream_wrapper.wait_for_docker", return_value=True), \
         patch("start_stream_wrapper.subprocess.run") as mock_run, \
         patch("start_stream_wrapper.exclusive_run") as mock_lock:
        mock_run.return_value = MagicMock(returncode=0)
        mock_lock.return_value.__enter__.return_value = None
        mock_lock.return_value.__exit__.return_value = False

        try:
            start_stream_wrapper.main()
        except SystemExit:
            pass

    actual_cmd = mock_run.call_args[0][0]
    assert actual_cmd == [
        expected_bin, "compose", "run", "--rm", "rct", "python", "scripts/start_stream.py"
    ]
