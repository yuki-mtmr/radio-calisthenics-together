"""P5 構造確認テスト — 抽出されたメソッド/削除された定数の存在確認。"""
import importlib


def test_obs_client_has_prepare_scene():
    from rct.obs_client import OBSClient
    assert hasattr(OBSClient, "_prepare_scene")


def test_obs_client_has_refresh_and_freeze_media():
    from rct.obs_client import OBSClient
    assert hasattr(OBSClient, "_refresh_and_freeze_media")


def test_obs_client_has_force_stop_if_stale():
    from rct.obs_client import OBSClient
    assert hasattr(OBSClient, "_force_stop_if_stale")


def test_orchestrator_has_no_docker_bin_constant():
    """DOCKER_BIN は orchestrator では不要な dead 定数 (docker_ops に移管済み)。"""
    import orchestrator
    importlib.reload(orchestrator)
    assert not hasattr(orchestrator, "DOCKER_BIN")


def test_health_monitor_has_launchd_issues_helper():
    import health_monitor
    importlib.reload(health_monitor)
    assert hasattr(health_monitor, "_launchd_issues")


def test_health_monitor_has_docker_issues_helper():
    import health_monitor
    importlib.reload(health_monitor)
    assert hasattr(health_monitor, "_docker_issues")


def test_health_monitor_has_log_issues_helper():
    import health_monitor
    importlib.reload(health_monitor)
    assert hasattr(health_monitor, "_log_issues")


def test_health_monitor_has_token_issues_helper():
    import health_monitor
    importlib.reload(health_monitor)
    assert hasattr(health_monitor, "_token_issues")
