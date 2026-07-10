#!/usr/bin/env python3
"""初回 OAuth 認証。youtube-autopost ライブラリの auth CLI に委譲する薄いラッパー。

トークンは authorized_user JSON 形式で config/youtube/token.json に保存される
(旧 token.pickle 形式ではない)。既存の token.pickle からの移行が必要な場合は
scripts/migrate_youtube_token.py を先に実行すること。

Usage:
    .venv/bin/python scripts/authenticate_youtube.py
"""
from youtube_autopost.auth_cli import main as auth_cli_main

if __name__ == "__main__":
    raise SystemExit(auth_cli_main())
