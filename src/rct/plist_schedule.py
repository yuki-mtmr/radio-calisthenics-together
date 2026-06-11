"""launchd plist の Hour/Minute 読み書きユーティリティ。gui_app から抽出。"""
from __future__ import annotations

import os
import re


def read_schedule(plist_path: str) -> tuple[int, int] | None:
    """plist から Hour/Minute を読み取り (hour, minute) を返す。ファイルが無ければ None。"""
    if not os.path.exists(plist_path):
        return None
    with open(plist_path, "r") as f:
        content = f.read()
    h = re.search(r"<key>Hour</key>\s*<integer>(\d+)</integer>", content)
    m = re.search(r"<key>Minute</key>\s*<integer>(\d+)</integer>", content)
    if h and m:
        return int(h.group(1)), int(m.group(1))
    return None


def write_schedule(plist_path: str, hour: int, minute: int) -> None:
    """plist の Hour/Minute を更新する。"""
    with open(plist_path, "r") as f:
        content = f.read()
    content = re.sub(
        r"(<key>Hour</key>\s*<integer>)\d+(</integer>)",
        rf"\g<1>{int(hour)}\g<2>",
        content,
    )
    content = re.sub(
        r"(<key>Minute</key>\s*<integer>)\d+(</integer>)",
        rf"\g<1>{int(minute)}\g<2>",
        content,
    )
    with open(plist_path, "w") as f:
        f.write(content)
