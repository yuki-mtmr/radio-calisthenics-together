"""rct.watchdog の仕様テスト (TDD: 実装より先に作成)。

7/7 インシデント: flock を握ったまま 3 日間生存するハングプロセスを誰も
発見できなかった。health_monitor が毎朝、対象スクリプトの経過時間 (ps の etime)
を確認し、2 時間を超えていれば強制 kill してアラートする。
"""
from unittest.mock import MagicMock

from rct import watchdog


# ------------------------------------------------------------------ parse_etime

def test_parse_etime_mm_ss():
    assert watchdog.parse_etime("05:30") == 5 * 60 + 30


def test_parse_etime_hh_mm_ss():
    assert watchdog.parse_etime("01:02:03") == 1 * 3600 + 2 * 60 + 3


def test_parse_etime_dd_hh_mm_ss():
    assert watchdog.parse_etime("2-01:02:03") == 2 * 86400 + 3600 + 120 + 3


def test_parse_etime_seconds_only():
    assert watchdog.parse_etime("45") == 45


# -------------------------------------------------------- find_stale_processes

def test_finds_process_older_than_max_age():
    ps_lines = [
        "  123 02:30:00 python3 scripts/orchestrator.py",
    ]
    stale = watchdog.find_stale_processes(
        ps_lines, target_names=watchdog.TARGET_SCRIPT_NAMES, max_age_seconds=7200
    )
    assert len(stale) == 1
    assert stale[0]["pid"] == 123
    assert stale[0]["name"] == "orchestrator.py"
    assert stale[0]["age_seconds"] == 2 * 3600 + 30 * 60


def test_ignores_process_younger_than_max_age():
    ps_lines = [
        "  123 00:10:00 python3 scripts/orchestrator.py",
    ]
    stale = watchdog.find_stale_processes(
        ps_lines, target_names=watchdog.TARGET_SCRIPT_NAMES, max_age_seconds=7200
    )
    assert stale == []


def test_ignores_unrelated_process():
    ps_lines = [
        "  123 05:00:00 /usr/sbin/some_daemon",
    ]
    stale = watchdog.find_stale_processes(
        ps_lines, target_names=watchdog.TARGET_SCRIPT_NAMES, max_age_seconds=7200
    )
    assert stale == []


def test_excludes_self_pid():
    """health_monitor 自身のプロセス (自分の pid) は除外する。"""
    ps_lines = [
        "  999 05:00:00 python3 scripts/health_monitor.py",
    ]
    stale = watchdog.find_stale_processes(
        ps_lines,
        target_names=watchdog.TARGET_SCRIPT_NAMES,
        max_age_seconds=7200,
        self_pid=999,
    )
    assert stale == []


def test_finds_multiple_stale_processes():
    ps_lines = [
        "  100 03:00:00 python3 scripts/orchestrator.py",
        "  200 04:00:00 python3 scripts/start_stream_wrapper.py",
        "  300 00:05:00 python3 scripts/health_monitor.py",
    ]
    stale = watchdog.find_stale_processes(
        ps_lines, target_names=watchdog.TARGET_SCRIPT_NAMES, max_age_seconds=7200
    )
    pids = sorted(p["pid"] for p in stale)
    assert pids == [100, 200]


def test_malformed_line_is_skipped():
    ps_lines = ["garbage line", ""]
    stale = watchdog.find_stale_processes(
        ps_lines, target_names=watchdog.TARGET_SCRIPT_NAMES, max_age_seconds=7200
    )
    assert stale == []


def test_ignores_less_viewing_the_script_file():
    """HIGH: `less scripts/prepare_environment.py` は誤って kill 対象にしてはいけない。

    リファクタ前は command 文字列への裸の部分一致だったため、対象スクリプト名を
    含むだけの無関係プロセス (less/grep/エディタ等) も stale 判定されてしまっていた。
    """
    ps_lines = [
        "  123 05:00:00 less scripts/prepare_environment.py",
    ]
    stale = watchdog.find_stale_processes(
        ps_lines, target_names=watchdog.TARGET_SCRIPT_NAMES, max_age_seconds=7200
    )
    assert stale == []


def test_ignores_grep_searching_for_script_name():
    ps_lines = [
        "  124 05:00:00 grep health_monitor.py foo.log",
    ]
    stale = watchdog.find_stale_processes(
        ps_lines, target_names=watchdog.TARGET_SCRIPT_NAMES, max_age_seconds=7200
    )
    assert stale == []


def test_ignores_editor_with_script_name_in_path():
    ps_lines = [
        "  125 05:00:00 vim /Users/x/projects/rct/scripts/orchestrator.py",
    ]
    stale = watchdog.find_stale_processes(
        ps_lines, target_names=watchdog.TARGET_SCRIPT_NAMES, max_age_seconds=7200
    )
    assert stale == []


def test_matches_python_interpreter_running_script():
    ps_lines = [
        "  126 05:00:00 python3 scripts/orchestrator.py",
    ]
    stale = watchdog.find_stale_processes(
        ps_lines, target_names=watchdog.TARGET_SCRIPT_NAMES, max_age_seconds=7200
    )
    assert len(stale) == 1
    assert stale[0]["pid"] == 126


def test_matches_python_with_version_suffix_and_absolute_path():
    ps_lines = [
        "  127 05:00:00 /usr/bin/python3.11 /abs/path/scripts/start_stream_wrapper.py --flag",
    ]
    stale = watchdog.find_stale_processes(
        ps_lines, target_names=watchdog.TARGET_SCRIPT_NAMES, max_age_seconds=7200
    )
    assert len(stale) == 1
    assert stale[0]["pid"] == 127


def test_matches_docker_compose_run_for_bird_director():
    """bird_director.py は `docker compose run rct python scripts/bird_director.py` 経由で
    常駐する。docker compose 実行体も明示的に対象とする。"""
    ps_lines = [
        "  128 05:00:00 docker compose run --rm rct python scripts/bird_director.py --duration 960",
    ]
    stale = watchdog.find_stale_processes(
        ps_lines, target_names=watchdog.TARGET_SCRIPT_NAMES, max_age_seconds=7200
    )
    assert len(stale) == 1
    assert stale[0]["pid"] == 128


# -------------------------------------------------------- kill_stale_processes

def test_kill_stale_processes_calls_kill_fn_for_each():
    stale = [
        {"pid": 1, "name": "orchestrator.py", "age_seconds": 8000, "command": "..."},
        {"pid": 2, "name": "start_stream_wrapper.py", "age_seconds": 9000, "command": "..."},
    ]
    kill_fn = MagicMock()

    killed = watchdog.kill_stale_processes(stale, kill_fn=kill_fn)

    assert kill_fn.call_count == 2
    assert len(killed) == 2


def test_kill_stale_processes_skips_already_dead():
    stale = [{"pid": 1, "name": "orchestrator.py", "age_seconds": 8000, "command": "..."}]

    def kill_fn(pid):
        raise ProcessLookupError()

    killed = watchdog.kill_stale_processes(stale, kill_fn=kill_fn)
    assert killed == []


# --------------------------------------------------- run_stale_process_watchdog

def test_run_watchdog_full_flow_kills_and_alerts():
    ps_lines = ["  123 05:00:00 python3 scripts/orchestrator.py"]
    kill_fn = MagicMock()
    alert_fn = MagicMock()

    killed = watchdog.run_stale_process_watchdog(
        get_ps_lines=lambda: ps_lines,
        kill_fn=kill_fn,
        alert_fn=alert_fn,
        max_age_seconds=7200,
    )

    assert len(killed) == 1
    kill_fn.assert_called_once_with(123)
    alert_fn.assert_called_once()


def test_run_watchdog_no_stale_no_alert():
    kill_fn = MagicMock()
    alert_fn = MagicMock()

    killed = watchdog.run_stale_process_watchdog(
        get_ps_lines=lambda: [], kill_fn=kill_fn, alert_fn=alert_fn
    )

    assert killed == []
    kill_fn.assert_not_called()
    alert_fn.assert_not_called()
