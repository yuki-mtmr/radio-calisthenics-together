"""token.pickle → token.json 移行スクリプトのテスト。

TDD opt-out: 一度きりの移行作業であり、恒久ロジックではないため、
pickle→JSON 変換の中核ロジックのみ最低限テストする。
"""
import pickle

from rct.migrate_youtube_token import migrate_pickle_token_to_json


class _FakeCreds:
    def __init__(self, json_str):
        self._json_str = json_str

    def to_json(self):
        return self._json_str


def test_migrate_pickle_token_to_json_writes_json_file(tmp_path):
    pickle_path = tmp_path / "token.pickle"
    json_path = tmp_path / "token.json"

    creds = _FakeCreds('{"token": "abc", "refresh_token": "xyz"}')
    with open(pickle_path, "wb") as f:
        pickle.dump(creds, f)

    migrate_pickle_token_to_json(str(pickle_path), str(json_path))

    assert json_path.read_text() == '{"token": "abc", "refresh_token": "xyz"}'


def test_migrate_pickle_token_to_json_raises_when_source_missing(tmp_path):
    import pytest

    with pytest.raises(FileNotFoundError):
        migrate_pickle_token_to_json(
            str(tmp_path / "nonexistent.pickle"), str(tmp_path / "token.json")
        )
