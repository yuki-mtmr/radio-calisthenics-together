"""video_library のテスト（配信動画選択機能）。"""


def test_list_videos_returns_only_supported_extensions_sorted(tmp_path):
    from rct.video_library import list_videos
    (tmp_path / "b.mp4").touch()
    (tmp_path / "A.MOV").touch()
    (tmp_path / "c.mkv").touch()
    (tmp_path / "note.txt").touch()
    (tmp_path / "d.wav").touch()
    assert [p.name for p in list_videos(tmp_path)] == ["A.MOV", "b.mp4", "c.mkv"]


def test_list_videos_returns_empty_for_missing_dir(tmp_path):
    from rct.video_library import list_videos
    assert list_videos(tmp_path / "nope") == []


def test_list_videos_ignores_hidden_and_appledouble(tmp_path):
    """macOS の AppleDouble (._*) や隠しファイルは外部ボリューム経由で混入しうる。"""
    from rct.video_library import list_videos
    (tmp_path / "._meta.mp4").touch()
    (tmp_path / ".hidden.mp4").touch()
    (tmp_path / "real.mp4").touch()
    assert [p.name for p in list_videos(tmp_path)] == ["real.mp4"]


def test_list_videos_ignores_directories(tmp_path):
    from rct.video_library import list_videos
    (tmp_path / "dir.mp4").mkdir()
    (tmp_path / "file.mp4").touch()
    assert [p.name for p in list_videos(tmp_path)] == ["file.mp4"]


def test_find_video_returns_path_or_none(tmp_path):
    from rct.video_library import find_video
    (tmp_path / "a.mp4").touch()
    found = find_video(tmp_path, "a.mp4")
    assert found is not None
    assert found.name == "a.mp4"
    assert find_video(tmp_path, "missing.mp4") is None


def test_is_env_safe_filename():
    """dotenv は「空白 + #」以降を截断し、改行・前後空白は値を壊すため拒否する。"""
    from rct.video_library import is_env_safe_filename
    # 受理: 日本語・全角括弧・内部スペース
    assert is_env_safe_filename("ラジオ体操第一（通し）.mp4")
    assert is_env_safe_filename("radio calisthenics 2026.mp4")
    # 拒否
    assert not is_env_safe_filename("video #2.mp4")
    assert not is_env_safe_filename(" pad.mp4")
    assert not is_env_safe_filename("pad.mp4 ")
    assert not is_env_safe_filename("a\nb.mp4")
    assert not is_env_safe_filename("")
