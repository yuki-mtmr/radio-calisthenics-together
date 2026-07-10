"""obs_quality.py のテスト。

2026-07-10 14:01 の配信で CPU 競合により OBS エンコード落ちフレームが 46.7% に
達しカクカクの VOD が公開されたが、既存の verify_stream (「live になったか」のみ)
では検知できなかった。OBS ログの Streaming Stop 統計を解析して品質劣化を検知する。
"""
from pathlib import Path

from rct.obs_quality import (
    find_latest_log_file,
    get_latest_session_quality,
    is_quality_degraded,
    parse_session_stats,
)

GOOD_SESSION_LOG = """\
19:00:00.000: ==== Streaming Start ====
19:00:01.000: Output 'simple_stream': Number of lagged frames due to rendering lag/stalls: 12 (0.1%)
19:00:01.000: Video stopped, number of skipped frames due to encoding lag: 5/12420 (0.0%)
19:00:01.000: Output 'simple_stream': Total frames output: 12420
19:00:02.000: ==== Streaming Stop ====
"""

BAD_SESSION_LOG = """\
19:00:00.000: ==== Streaming Start ====
19:00:01.000: Output 'simple_stream': Number of lagged frames due to rendering lag/stalls: 3230 (25.9%)
19:00:01.000: Video stopped, number of skipped frames due to encoding lag: 5795/12420 (46.7%)
19:00:01.000: Output 'simple_stream': Total frames output: 11735
19:00:02.000: ==== Streaming Stop ====
"""

NO_STATS_LOG = """\
19:00:00.000: ==== Streaming Start ====
19:00:02.000: ==== Streaming Stop ====
"""

MULTI_SESSION_LOG = f"""\
{BAD_SESSION_LOG}
19:10:00.000: ==== Streaming Start ====
19:10:01.000: Output 'simple_stream': Number of lagged frames due to rendering lag/stalls: 4 (0.05%)
19:10:01.000: Video stopped, number of skipped frames due to encoding lag: 1/9000 (0.01%)
19:10:01.000: Output 'simple_stream': Total frames output: 9000
19:10:02.000: ==== Streaming Stop ====
"""


class TestParseSessionStats:
    def test_parses_good_session(self):
        stats = parse_session_stats(GOOD_SESSION_LOG)
        assert stats.rendering_lag_pct == 0.1
        assert stats.encoding_skip_pct == 0.0
        assert stats.encoding_skip_frames == 5
        assert stats.encoding_total_frames == 12420
        assert stats.total_frames == 12420

    def test_parses_bad_session(self):
        stats = parse_session_stats(BAD_SESSION_LOG)
        assert stats.rendering_lag_pct == 25.9
        assert stats.rendering_lag_frames == 3230
        assert stats.encoding_skip_pct == 46.7
        assert stats.encoding_skip_frames == 5795
        assert stats.encoding_total_frames == 12420
        assert stats.total_frames == 11735

    def test_missing_stat_lines_yield_none_fields(self):
        stats = parse_session_stats(NO_STATS_LOG)
        assert stats.rendering_lag_pct is None
        assert stats.encoding_skip_pct is None
        assert stats.total_frames is None

    def test_uses_last_session_when_multiple_present(self):
        """複数セッションがログに存在する場合、最後の Streaming Stop 直前の統計を使う。"""
        stats = parse_session_stats(MULTI_SESSION_LOG)
        assert stats.rendering_lag_pct == 0.05
        assert stats.encoding_skip_pct == 0.01
        assert stats.total_frames == 9000

    def test_empty_text_returns_all_none(self):
        stats = parse_session_stats("")
        assert stats.rendering_lag_pct is None
        assert stats.encoding_skip_pct is None
        assert stats.total_frames is None


class TestIsQualityDegraded:
    def test_ok_below_threshold(self):
        stats = parse_session_stats(GOOD_SESSION_LOG)
        assert is_quality_degraded(stats) is False

    def test_ng_rendering_lag_above_threshold(self):
        stats = parse_session_stats(BAD_SESSION_LOG)
        assert is_quality_degraded(stats) is True

    def test_ng_encoding_skip_above_threshold(self):
        stats = parse_session_stats(BAD_SESSION_LOG)
        assert is_quality_degraded(stats, threshold=30.0) is True  # encoding 46.7% > 30

    def test_custom_threshold_ok(self):
        stats = parse_session_stats(BAD_SESSION_LOG)
        assert is_quality_degraded(stats, threshold=50.0) is False

    def test_none_fields_are_not_degraded(self):
        stats = parse_session_stats(NO_STATS_LOG)
        assert is_quality_degraded(stats) is False


class TestFindLatestLogFile:
    def test_returns_none_when_dir_missing(self, tmp_path):
        missing = tmp_path / "does-not-exist"
        assert find_latest_log_file(missing) is None

    def test_returns_none_when_dir_empty(self, tmp_path):
        assert find_latest_log_file(tmp_path) is None

    def test_returns_most_recently_modified_file(self, tmp_path):
        old = tmp_path / "2026-07-09 06-59-00.txt"
        old.write_text("old", encoding="utf-8")
        new = tmp_path / "2026-07-10 06-59-00.txt"
        new.write_text("new", encoding="utf-8")
        import os
        import time

        old_time = time.time() - 100
        os.utime(old, (old_time, old_time))

        result = find_latest_log_file(tmp_path)
        assert result == new

    def test_expands_user_home(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        log_file = tmp_path / "session.txt"
        log_file.write_text("data", encoding="utf-8")
        result = find_latest_log_file("~")
        assert result == log_file


class TestGetLatestSessionQuality:
    def test_returns_none_when_no_log_dir(self, tmp_path):
        assert get_latest_session_quality(tmp_path / "missing") is None

    def test_reads_and_parses_latest_log(self, tmp_path):
        log_file = tmp_path / "2026-07-10 14-01-00.txt"
        log_file.write_text(BAD_SESSION_LOG, encoding="utf-8")

        stats = get_latest_session_quality(tmp_path)

        assert stats is not None
        assert stats.encoding_skip_pct == 46.7
        assert stats.source_log == log_file.name

    def test_returns_none_on_unreadable_file(self, tmp_path, monkeypatch):
        log_file = tmp_path / "broken.txt"
        log_file.write_text("data", encoding="utf-8")

        def _boom(*args, **kwargs):
            raise OSError("boom")

        monkeypatch.setattr(Path, "read_text", _boom)
        assert get_latest_session_quality(tmp_path) is None
