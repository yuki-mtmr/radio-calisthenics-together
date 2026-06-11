"""P6 GUI ユーティリティ抽出テスト (gui_app は customtkinter が無いため import しない)。"""
import pytest
import os


# ---------------------------------------------------------------- env_file


def test_read_env_value_returns_default_when_file_missing(tmp_path):
    from rct.env_file import read_env_value
    assert read_env_value(str(tmp_path / ".env"), "KEY", "default") == "default"


def test_read_env_value_returns_value(tmp_path):
    from rct.env_file import read_env_value
    env = tmp_path / ".env"
    env.write_text("FOO=bar\nBAZ=qux\n")
    assert read_env_value(str(env), "FOO", "") == "bar"
    assert read_env_value(str(env), "BAZ", "") == "qux"
    assert read_env_value(str(env), "MISSING", "d") == "d"


def test_update_env_values_updates_existing(tmp_path):
    from rct.env_file import update_env_values
    env = tmp_path / ".env"
    env.write_text("FOO=old\nBAR=keep\n")
    update_env_values(str(env), {"FOO": "new"})
    lines = env.read_text().splitlines()
    assert "FOO=new" in lines
    assert "BAR=keep" in lines


def test_update_env_values_appends_new_key(tmp_path):
    from rct.env_file import update_env_values
    env = tmp_path / ".env"
    env.write_text("FOO=old\n")
    update_env_values(str(env), {"NEW_KEY": "val"})
    assert "NEW_KEY=val" in env.read_text()


def test_update_env_values_creates_file_if_missing(tmp_path):
    from rct.env_file import update_env_values
    env = tmp_path / ".env"
    update_env_values(str(env), {"K": "v"})
    assert env.exists()
    assert "K=v" in env.read_text()


# ---------------------------------------------------------------- plist_schedule


SAMPLE_PLIST = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>59</integer>
    </dict>
</dict>
</plist>
"""


def test_read_schedule_returns_hour_minute(tmp_path):
    from rct.plist_schedule import read_schedule
    p = tmp_path / "test.plist"
    p.write_text(SAMPLE_PLIST)
    result = read_schedule(str(p))
    assert result == (6, 59)


def test_read_schedule_returns_none_when_file_missing(tmp_path):
    from rct.plist_schedule import read_schedule
    assert read_schedule(str(tmp_path / "nonexistent.plist")) is None


def test_write_schedule_updates_hour_minute(tmp_path):
    from rct.plist_schedule import read_schedule, write_schedule
    p = tmp_path / "test.plist"
    p.write_text(SAMPLE_PLIST)
    write_schedule(str(p), 7, 5)
    assert read_schedule(str(p)) == (7, 5)


def test_write_schedule_preserves_other_content(tmp_path):
    from rct.plist_schedule import write_schedule
    p = tmp_path / "test.plist"
    p.write_text(SAMPLE_PLIST)
    write_schedule(str(p), 7, 0)
    content = p.read_text()
    assert "StartCalendarInterval" in content
    assert "<integer>7</integer>" in content
    assert "<integer>0</integer>" in content


# ------------------------------------ env_file × dotenv ラウンドトリップ特性


def test_update_env_values_roundtrips_via_dotenv_with_japanese_and_spaces(tmp_path):
    """OBS_MEDIA_FILE_PATH に入る日本語+スペースのパスが dotenv 経由で壊れないことを pin する。

    dotenv パーサは引用符なし値でも内部スペース・日本語を保持する（parser.py 確認済み）。
    将来の python-dotenv 更新で挙動が変わった場合、ここで検知する。
    """
    from dotenv import dotenv_values
    from rct.env_file import update_env_values
    env = tmp_path / ".env"
    path_value = "/Users/x/videos/ラジオ体操 第一（通し）.mp4"
    update_env_values(str(env), {"OBS_MEDIA_FILE_PATH": path_value})
    assert dotenv_values(str(env))["OBS_MEDIA_FILE_PATH"] == path_value


def test_read_env_value_agrees_with_dotenv_for_path_values(tmp_path):
    """GUI (read_env_value) とコンテナ (dotenv/load_dotenv) が同じ値を読むことを保証する。"""
    from dotenv import dotenv_values
    from rct.env_file import read_env_value, update_env_values
    env = tmp_path / ".env"
    path_value = "/Users/x/videos/ラジオ体操 第一（通し）.mp4"
    update_env_values(str(env), {"OBS_MEDIA_FILE_PATH": path_value})
    assert read_env_value(str(env), "OBS_MEDIA_FILE_PATH", "") == path_value
    assert read_env_value(str(env), "OBS_MEDIA_FILE_PATH", "") == dotenv_values(str(env))[
        "OBS_MEDIA_FILE_PATH"
    ]
