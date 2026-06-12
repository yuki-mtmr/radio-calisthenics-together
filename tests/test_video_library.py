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


# ---------------------- メタデータ付き列挙 (Phase1 生成パイプライン) ----------


def _sentinel_info(**overrides):
    from rct.media_probe import MediaInfo
    base = dict(
        width=1920,
        height=1080,
        duration_sec=207.6,
        has_audio=True,
        video_codec="h264",
        audio_codec="aac",
        fps=30.0,
    )
    return MediaInfo(**{**base, **overrides})


def test_list_videos_with_info_pairs_paths_with_probe(tmp_path, monkeypatch):
    from rct import media_probe
    from rct.video_library import list_videos_with_info
    (tmp_path / "b.mp4").touch()
    (tmp_path / "a.mp4").touch()
    sentinel = _sentinel_info()
    seen = []

    def fake(path, *, cache_path=None, runner=None):
        seen.append(cache_path)
        return sentinel

    monkeypatch.setattr(media_probe, "get_media_info_cached", fake)
    result = list_videos_with_info(tmp_path)
    assert [(p.name, info) for p, info in result] == [("a.mp4", sentinel), ("b.mp4", sentinel)]
    # キャッシュは videos ディレクトリ直下の隠しファイル (list_videos からは除外される)
    assert all(c == tmp_path / ".media_meta.json" for c in seen)


def test_list_videos_with_info_probe_failure_gives_none(tmp_path, monkeypatch):
    from rct import media_probe
    from rct.video_library import list_videos_with_info
    (tmp_path / "a.mp4").touch()
    monkeypatch.setattr(media_probe, "get_media_info_cached", lambda *a, **k: None)
    result = list_videos_with_info(tmp_path)
    assert len(result) == 1
    assert result[0][1] is None


def test_format_media_label_full():
    from rct.video_library import format_media_label
    assert format_media_label(_sentinel_info()) == "1920×1080 / 3:28 / 音声あり"


def test_format_media_label_no_audio():
    from rct.video_library import format_media_label
    info = _sentinel_info(width=1280, height=720, duration_sec=60.0, has_audio=False, audio_codec=None)
    assert format_media_label(info) == "1280×720 / 1:00 / 音声なし"


def test_format_media_label_unknown_duration():
    from rct.video_library import format_media_label
    info = _sentinel_info(duration_sec=None)
    assert format_media_label(info) == "1920×1080 / -:-- / 音声あり"


def test_format_media_label_none():
    from rct.video_library import format_media_label
    assert format_media_label(None) == "メタデータ取得不可"
