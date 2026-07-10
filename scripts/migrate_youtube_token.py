#!/usr/bin/env python3
"""一度きりの移行スクリプト: config/youtube/token.pickle → config/youtube/token.json

youtube-autopost ライブラリへの移行 (2026-07) に伴い、token 保存形式が
pickle → authorized_user JSON に変わったため、本番の既存トークンを変換する。

Usage:
    .venv/bin/python scripts/migrate_youtube_token.py

実行後、config/youtube/token.json が生成されたことを確認したら
旧 token.pickle は削除して構わない (このスクリプトは削除しない — 手動確認後に削除)。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from rct.migrate_youtube_token import migrate_pickle_token_to_json

PICKLE_PATH = "config/youtube/token.pickle"
JSON_PATH = "config/youtube/token.json"


def main() -> int:
    if not os.path.exists(PICKLE_PATH):
        print(f"{PICKLE_PATH} が見つかりません。移行不要か、既に完了しています。")
        return 0

    if os.path.exists(JSON_PATH):
        print(f"{JSON_PATH} は既に存在します。上書きしません。移行済みの可能性があります。")
        return 1

    migrate_pickle_token_to_json(PICKLE_PATH, JSON_PATH)
    print(f"移行完了: {PICKLE_PATH} -> {JSON_PATH}")
    print("動作確認後、旧 token.pickle は手動で削除してください。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
