"""env ファイルの読み書きユーティリティ。gui_app から抽出。"""
from __future__ import annotations

import os


def read_env_value(env_path: str, key: str, default: str = "") -> str:
    """指定した .env ファイルから key の値を読み取る。"""
    if not os.path.exists(env_path):
        return default
    with open(env_path, "r") as f:
        for line in f:
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return default


def update_env_values(env_path: str, updates: dict[str, str]) -> None:
    """指定した .env ファイルの key=value を更新/追加する。"""
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.readlines()
    else:
        lines = []

    new_lines = []
    found_keys: set[str] = set()
    for line in lines:
        key = line.split("=")[0].strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}\n")
            found_keys.add(key)
        else:
            new_lines.append(line)
    for k, v in updates.items():
        if k not in found_keys:
            new_lines.append(f"{k}={v}\n")

    with open(env_path, "w") as f:
        f.writelines(new_lines)
