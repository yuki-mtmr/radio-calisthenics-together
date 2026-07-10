"""token.pickle (旧形式) → token.json (authorized_user JSON, youtube-autopost 形式) 移行。

一度きりの移行ロジック。恒久機能ではないため、TDD は中核の変換関数のみに絞る
(tests/test_migrate_youtube_token.py)。
"""
import os
import pickle


def migrate_pickle_token_to_json(pickle_path: str, json_path: str) -> None:
    """pickle 形式の Credentials を読み込み、authorized_user JSON として書き出す。"""
    if not os.path.exists(pickle_path):
        raise FileNotFoundError(f"Source pickle token not found: {pickle_path}")

    with open(pickle_path, "rb") as f:
        creds = pickle.load(f)

    json_dir = os.path.dirname(json_path)
    if json_dir and not os.path.exists(json_dir):
        os.makedirs(json_dir)

    fd = os.open(json_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(creds.to_json())
