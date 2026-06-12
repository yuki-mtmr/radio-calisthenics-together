"""media_probe のテスト(ffprobe ラッパ + sidecar キャッシュ)。

Docker テスト環境には ffprobe が無いため、パースは文字列フィクスチャ、
実行系は runner 注入でテストする。実 ffprobe はホストでの手動検証に委ねる。
"""
import json

import pytest

FFPROBE_JSON_AV = json.dumps(
    {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "avg_frame_rate": "30/1",
            },
            {"codec_type": "audio", "codec_name": "aac"},
        ],
        "format": {"duration": "207.600000"},
    }
)

FFPROBE_JSON_VIDEO_ONLY = json.dumps(
    {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1280,
                "height": 720,
                "avg_frame_rate": "30000/1001",
            }
        ],
        "format": {"duration": "60.0"},
    }
)


def _fake_runner(stdout, returncode=0):
    from rct.command_runner import CommandResult

    calls = []

    def runner(cmd):
        calls.append(list(cmd))
        return CommandResult(returncode=returncode, stdout=stdout, stderr="")

    runner.calls = calls
    return runner


def test_parse_ffprobe_json_av():
    from rct.media_probe import parse_ffprobe_json
    info = parse_ffprobe_json(FFPROBE_JSON_AV)
    assert info.width == 1920
    assert info.height == 1080
    assert info.duration_sec == pytest.approx(207.6)
    assert info.has_audio is True
    assert info.video_codec == "h264"
    assert info.audio_codec == "aac"
    assert info.fps == pytest.approx(30.0)


def test_parse_ffprobe_json_video_only():
    from rct.media_probe import parse_ffprobe_json
    info = parse_ffprobe_json(FFPROBE_JSON_VIDEO_ONLY)
    assert info.has_audio is False
    assert info.audio_codec is None
    assert info.fps == pytest.approx(29.97, abs=0.01)


def test_parse_ffprobe_json_tolerates_missing_fields():
    from rct.media_probe import parse_ffprobe_json
    info = parse_ffprobe_json('{"streams": [], "format": {}}')
    assert info.width is None
    assert info.duration_sec is None
    assert info.has_audio is False


def test_ffprobe_command_shape(tmp_path):
    from rct.media_probe import ffprobe_command
    p = tmp_path / "a.mp4"
    cmd = ffprobe_command(p)
    assert cmd[0] == "ffprobe"
    assert "-print_format" in cmd and "json" in cmd
    assert "-show_streams" in cmd and "-show_format" in cmd
    assert cmd[-1] == str(p)


def test_probe_media_returns_none_when_ffprobe_missing(tmp_path, monkeypatch):
    import shutil
    from rct.media_probe import probe_media
    monkeypatch.setattr(shutil, "which", lambda _: None)
    p = tmp_path / "a.mp4"
    p.touch()
    assert probe_media(p) is None


def test_probe_media_with_injected_runner(tmp_path):
    from rct.media_probe import probe_media
    runner = _fake_runner(FFPROBE_JSON_AV)
    p = tmp_path / "a.mp4"
    p.touch()
    info = probe_media(p, runner=runner)
    assert info is not None and info.width == 1920
    assert len(runner.calls) == 1


def test_probe_media_returns_none_on_failure(tmp_path):
    from rct.media_probe import probe_media
    runner = _fake_runner("", returncode=1)
    p = tmp_path / "a.mp4"
    p.touch()
    assert probe_media(p, runner=runner) is None


def test_probe_media_returns_none_on_bad_json(tmp_path):
    from rct.media_probe import probe_media
    runner = _fake_runner("not json")
    p = tmp_path / "a.mp4"
    p.touch()
    assert probe_media(p, runner=runner) is None


def test_get_media_info_cached_caches_and_invalidates(tmp_path):
    from rct.media_probe import get_media_info_cached
    video = tmp_path / "a.mp4"
    video.write_bytes(b"xx")
    cache = tmp_path / ".media_meta.json"

    runner = _fake_runner(FFPROBE_JSON_AV)
    info1 = get_media_info_cached(video, cache_path=cache, runner=runner)
    info2 = get_media_info_cached(video, cache_path=cache, runner=runner)
    assert info1 is not None and info1 == info2
    assert len(runner.calls) == 1, "2回目はキャッシュから返す"
    assert cache.exists()

    # サイズ変更でキャッシュ失効
    video.write_bytes(b"xxxx")
    info3 = get_media_info_cached(video, cache_path=cache, runner=runner)
    assert info3 is not None
    assert len(runner.calls) == 2, "ファイル変更後は再 probe する"


def test_get_media_info_cached_survives_corrupt_cache(tmp_path):
    from rct.media_probe import get_media_info_cached
    video = tmp_path / "a.mp4"
    video.write_bytes(b"xx")
    cache = tmp_path / ".media_meta.json"
    cache.write_text("{{{ not json")

    runner = _fake_runner(FFPROBE_JSON_AV)
    info = get_media_info_cached(video, cache_path=cache, runner=runner)
    assert info is not None and info.width == 1920


def test_get_media_info_cached_returns_none_when_probe_unavailable(tmp_path, monkeypatch):
    import shutil
    from rct.media_probe import get_media_info_cached
    monkeypatch.setattr(shutil, "which", lambda _: None)
    video = tmp_path / "a.mp4"
    video.write_bytes(b"xx")
    cache = tmp_path / ".media_meta.json"
    assert get_media_info_cached(video, cache_path=cache) is None
    # probe 失敗はキャッシュに保存しない(次回 ffprobe が入ったら probe できるように)
    runner = _fake_runner(FFPROBE_JSON_AV)
    assert get_media_info_cached(video, cache_path=cache, runner=runner) is not None
