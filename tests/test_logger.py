"""logger.py の characterization テスト。

`rct_YYYYMMDD.log` の命名は翌朝観測ゲート (logs/rct_YYYYMMDD.log の確認) が
依存する runtime 契約。リファクタで壊れていないことをここで監視する。
"""
import logging
import re

from rct.logger import setup_logger


def _teardown(logger):
    """テスト間の handler 汚染を防ぐ。"""
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


def test_creates_log_dir_and_dated_file(tmp_path):
    """log_dir が無ければ作成し、<name>_YYYYMMDD.log を生成する。"""
    log_dir = tmp_path / "logs"
    logger = setup_logger(log_dir=str(log_dir), name="rct_test_dated")
    try:
        assert log_dir.exists()
        files = list(log_dir.glob("*.log"))
        assert len(files) == 1
        assert re.fullmatch(r"rct_test_dated_\d{8}\.log", files[0].name)
    finally:
        _teardown(logger)


def test_console_and_file_handlers_attached(tmp_path):
    """StreamHandler + FileHandler の 2 本構成。"""
    logger = setup_logger(log_dir=str(tmp_path), name="rct_test_handlers")
    try:
        assert len(logger.handlers) == 2
        kinds = {type(h) for h in logger.handlers}
        assert logging.StreamHandler in kinds
        assert logging.FileHandler in kinds
    finally:
        _teardown(logger)


def test_repeat_call_does_not_duplicate_handlers(tmp_path):
    """同名 logger の再 setup で handler が増えない (全 script が module level で呼ぶ前提)。"""
    first = setup_logger(log_dir=str(tmp_path), name="rct_test_dedup")
    try:
        count = len(first.handlers)
        second = setup_logger(log_dir=str(tmp_path), name="rct_test_dedup")
        assert second is first
        assert len(second.handlers) == count
    finally:
        _teardown(first)


def test_log_line_format(tmp_path):
    """ログ行は 'asctime - name - LEVEL - message' 形式 (health_monitor のログ grep が依存)。"""
    logger = setup_logger(log_dir=str(tmp_path), name="rct_test_format")
    try:
        logger.info("format check message")
        for handler in logger.handlers:
            handler.flush()
        log_file = next(tmp_path.glob("rct_test_format_*.log"))
        content = log_file.read_text()
        assert re.search(
            r"\d{4}-\d{2}-\d{2} .* - rct_test_format - INFO - format check message",
            content,
        )
    finally:
        _teardown(logger)
