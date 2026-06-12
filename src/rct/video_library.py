"""動画ストック (videos/) の列挙と選択値の検証。管理パネル (gui_app) から利用する。"""
from __future__ import annotations

from pathlib import Path

from rct import media_probe

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".mkv"}
# 隠しファイルなので list_videos の列挙からは自動的に除外される
MEDIA_CACHE_FILENAME = ".media_meta.json"


def list_videos(directory: str | Path) -> list[Path]:
    """directory 直下の動画ファイルを名前順 (大文字小文字無視) で返す。

    隠しファイル (macOS の AppleDouble `._*` を含む) とディレクトリは除外する。
    ディレクトリが存在しなければ空リスト。
    """
    d = Path(directory)
    if not d.is_dir():
        return []
    videos = [
        p
        for p in d.iterdir()
        if p.is_file()
        and not p.name.startswith(".")
        and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(videos, key=lambda p: p.name.lower())


def find_video(directory: str | Path, name: str) -> Path | None:
    """directory 内で name に一致する動画を返す。無ければ None。"""
    for p in list_videos(directory):
        if p.name == name:
            return p
    return None


def list_videos_with_info(
    directory: str | Path,
    *,
    runner: media_probe.Runner | None = None,
) -> list[tuple[Path, media_probe.MediaInfo | None]]:
    """list_videos と同順で (パス, メタデータ) を返す。probe 不能な動画は None。

    メタデータは directory/.media_meta.json にキャッシュされる (size/mtime 失効)。
    """
    d = Path(directory)
    cache_path = d / MEDIA_CACHE_FILENAME
    return [
        (p, media_probe.get_media_info_cached(p, cache_path=cache_path, runner=runner))
        for p in list_videos(d)
    ]


def format_media_label(info: media_probe.MediaInfo | None) -> str:
    """GUI 表示用の 1 行ラベル。例: "1920×1080 / 3:28 / 音声あり"。"""
    if info is None:
        return "メタデータ取得不可"
    if info.width and info.height:
        res = f"{info.width}×{info.height}"
    else:
        res = "?×?"
    if info.duration_sec is None:
        dur = "-:--"
    else:
        total = round(info.duration_sec)
        dur = f"{total // 60}:{total % 60:02d}"
    audio = "音声あり" if info.has_audio else "音声なし"
    return f"{res} / {dur} / {audio}"


def is_env_safe_filename(name: str) -> bool:
    """.env の値として安全なファイル名か判定する。

    dotenv パーサは引用符なしの値でも日本語・内部スペースを保持するが、
    「空白 + #」以降をコメントとして截断する。改行・前後空白も値を壊すため、
    `#`・改行・前後空白を含む名前を拒否する。
    """
    if not name or name != name.strip():
        return False
    if "#" in name or "\n" in name or "\r" in name:
        return False
    return True
