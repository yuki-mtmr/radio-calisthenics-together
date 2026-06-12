"""command_runner のテスト (dry_run / 実行 / 失敗捕捉)。"""
import sys


def test_runner_dry_run_does_not_execute():
    from rct.command_runner import run_command
    result = run_command(["definitely-not-a-binary-xyz"], dry_run=True)
    assert result.returncode == 0


def test_runner_executes_real_command():
    from rct.command_runner import run_command
    result = run_command([sys.executable, "-c", "print('hello')"])
    assert result.returncode == 0
    assert "hello" in result.stdout


def test_runner_captures_failure():
    from rct.command_runner import run_command
    result = run_command([sys.executable, "-c", "import sys; sys.exit(3)"])
    assert result.returncode == 3
