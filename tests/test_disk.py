"""rct.disk のテスト

2026-08-06 インシデント由来: ホストのディスク満杯 (ENOSPC) で YouTube トークン
更新・verify・stop が全滅し、配信が一度も live にならなかった。空き容量を
ok / warn / critical の 3 段階で判定し、critical では配信フローを止められる
ようにするためのドメインロジック。
"""
import pytest

from rct.disk import (
    CRITICAL_LEVEL,
    OK_LEVEL,
    WARN_LEVEL,
    DiskStatus,
    check_free_space,
)

GB = 1024 ** 3


def _usage(free_gb):
    """shutil.disk_usage 互換の戻り値を作る注入用ヘルパ。"""
    total = 460 * GB
    free = int(free_gb * GB)
    return (total, total - free, free)


class TestCheckFreeSpace:
    def test_plenty_of_space_is_ok(self):
        status = check_free_space(
            "/", critical_gb=5, warn_gb=20, usage_fn=lambda p: _usage(100)
        )
        assert status.level == OK_LEVEL
        assert status.free_gb == pytest.approx(100.0, abs=0.01)

    def test_below_warn_threshold_is_warn(self):
        status = check_free_space(
            "/", critical_gb=5, warn_gb=20, usage_fn=lambda p: _usage(12)
        )
        assert status.level == WARN_LEVEL

    def test_below_critical_threshold_is_critical(self):
        status = check_free_space(
            "/", critical_gb=5, warn_gb=20, usage_fn=lambda p: _usage(2)
        )
        assert status.level == CRITICAL_LEVEL

    def test_exactly_at_warn_threshold_is_ok(self):
        """境界は「閾値未満」で発火する。閾値ちょうどは正常側。"""
        status = check_free_space(
            "/", critical_gb=5, warn_gb=20, usage_fn=lambda p: _usage(20)
        )
        assert status.level == OK_LEVEL

    def test_exactly_at_critical_threshold_is_warn_not_critical(self):
        status = check_free_space(
            "/", critical_gb=5, warn_gb=20, usage_fn=lambda p: _usage(5)
        )
        assert status.level == WARN_LEVEL

    def test_zero_free_is_critical(self):
        """2026-08-06 の実際の状況 (ENOSPC) を再現するケース。"""
        status = check_free_space(
            "/", critical_gb=5, warn_gb=20, usage_fn=lambda p: _usage(0)
        )
        assert status.level == CRITICAL_LEVEL

    def test_usage_fn_receives_the_given_path(self):
        seen = []

        def _spy(path):
            seen.append(path)
            return _usage(50)

        check_free_space("/some/path", critical_gb=5, warn_gb=20, usage_fn=_spy)
        assert seen == ["/some/path"]

    def test_message_contains_free_gb_and_path(self):
        status = check_free_space(
            "/repo", critical_gb=5, warn_gb=20, usage_fn=lambda p: _usage(1.5)
        )
        assert "1.5" in status.message
        assert "/repo" in status.message

    def test_usage_error_is_reported_as_critical(self):
        """空き容量が読めない状況自体が異常。安全側 (critical) に倒す。"""

        def _boom(path):
            raise OSError("boom")

        status = check_free_space(
            "/", critical_gb=5, warn_gb=20, usage_fn=_boom
        )
        assert status.level == CRITICAL_LEVEL
        assert "boom" in status.message

    def test_status_is_immutable(self):
        status = check_free_space(
            "/", critical_gb=5, warn_gb=20, usage_fn=lambda p: _usage(50)
        )
        with pytest.raises(Exception):
            status.level = OK_LEVEL


class TestDiskStatusHelpers:
    def test_is_critical_true_only_for_critical(self):
        assert DiskStatus(CRITICAL_LEVEL, 1.0, "m").is_critical is True
        assert DiskStatus(WARN_LEVEL, 10.0, "m").is_critical is False
        assert DiskStatus(OK_LEVEL, 100.0, "m").is_critical is False

    def test_is_ok_true_only_for_ok(self):
        assert DiskStatus(OK_LEVEL, 100.0, "m").is_ok is True
        assert DiskStatus(WARN_LEVEL, 10.0, "m").is_ok is False


class TestDefaultsUseRealFilesystem:
    def test_usage_fn_defaults_to_shutil_disk_usage(self):
        """注入なしでも実 FS を見て動く (本番経路)。"""
        status = check_free_space(".", critical_gb=0, warn_gb=0)
        assert status.free_gb > 0
        assert status.level == OK_LEVEL
