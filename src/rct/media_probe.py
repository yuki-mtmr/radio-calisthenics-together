"""ffprobe ラッパ + sidecar キャッシュ。

gui_app (選択動画のメタデータ表示) で使用。生成パイプラインは別リポジトリ
radio-calisthenics-studio に分離されており、そちらは同型の studio/probe.py を持つ。
ffprobe が無い環境 (Docker テストコンテナ等) では例外にせず None を返す。

キャッシュは videos/.media_meta.json (隠しファイルなので video_library の列挙
からは自動的に除外される)。ファイルの size/mtime が変わったら失効する。
"""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

from rct.command_runner import CommandResult, run_command

Runner = Callable[[Sequence[str]], CommandResult]


@dataclass(frozen=True)
class MediaInfo:
    width: int | None
    height: int | None
    duration_sec: float | None
    has_audio: bool
    video_codec: str | None
    audio_codec: str | None
    fps: float | None


def ffprobe_command(path: str | Path) -> list[str]:
    """メディア情報を JSON で取得する ffprobe コマンドを構築する。"""
    return [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]


def _parse_fps(rate: str | None) -> float | None:
    """ffprobe の avg_frame_rate ("30/1", "30000/1001") を float に変換する。"""
    if not rate:
        return None
    try:
        num_s, _, den_s = rate.partition("/")
        num = float(num_s)
        den = float(den_s) if den_s else 1.0
        if den == 0:
            return None
        return num / den
    except ValueError:
        return None


def parse_ffprobe_json(text: str) -> MediaInfo:
    """ffprobe の JSON 出力を MediaInfo に変換する。欠損フィールドは None。"""
    data = json.loads(text)
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration_raw = (data.get("format") or {}).get("duration")
    try:
        duration = float(duration_raw) if duration_raw is not None else None
    except (TypeError, ValueError):
        duration = None

    return MediaInfo(
        width=video.get("width") if video else None,
        height=video.get("height") if video else None,
        duration_sec=duration,
        has_audio=audio is not None,
        video_codec=video.get("codec_name") if video else None,
        audio_codec=audio.get("codec_name") if audio else None,
        fps=_parse_fps(video.get("avg_frame_rate")) if video else None,
    )


def probe_media(path: str | Path, *, runner: Runner | None = None) -> MediaInfo | None:
    """ffprobe でメディア情報を取得する。取得できない場合は None (例外にしない)。"""
    if runner is None:
        if shutil.which("ffprobe") is None:
            return None
        runner = run_command
    result = runner(ffprobe_command(path))
    if result.returncode != 0:
        return None
    try:
        return parse_ffprobe_json(result.stdout)
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
        return None


def _load_cache(cache_path: Path) -> dict:
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(cache_path: Path, cache: dict) -> None:
    """ベストエフォート保存 (読み取り専用ボリューム等では黙って諦める)。"""
    try:
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def get_media_info_cached(
    path: str | Path,
    *,
    cache_path: str | Path,
    runner: Runner | None = None,
) -> MediaInfo | None:
    """sidecar キャッシュ付きの probe。size/mtime 一致ならキャッシュを返す。

    probe 失敗 (ffprobe 不在含む) はキャッシュしない — 環境が直れば次回成功する。
    """
    p = Path(path)
    cache_file = Path(cache_path)
    try:
        stat = p.stat()
    except OSError:
        return None

    cache = _load_cache(cache_file)
    entry = cache.get(p.name)
    if (
        isinstance(entry, dict)
        and entry.get("size") == stat.st_size
        and entry.get("mtime") == stat.st_mtime
    ):
        try:
            return MediaInfo(**entry["info"])
        except (KeyError, TypeError):
            pass  # 互換性のない旧キャッシュ → 再 probe

    info = probe_media(p, runner=runner)
    if info is None:
        return None
    new_cache = {
        **cache,
        p.name: {"size": stat.st_size, "mtime": stat.st_mtime, "info": asdict(info)},
    }
    _save_cache(cache_file, new_cache)
    return info
