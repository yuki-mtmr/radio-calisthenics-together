"""動画ストック (videos/) の列挙と選択値の検証。管理パネル (gui_app) から利用する。"""
from __future__ import annotations

from pathlib import Path

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".mkv"}


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
