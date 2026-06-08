"""pytest 共有設定: import パスをプロジェクト構造に合わせて統一する。

`from scripts.start_stream import main` と `import prepare_environment` の
両方を、テスト単独実行でも全件実行でも同様に解決できるようにする。

(Docker compose は ./tests を mount するため、tests/ 配下に conftest.py を
置く必要がある。)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
for path in (ROOT, ROOT / "src", ROOT / "scripts"):
    p = str(path)
    if p not in sys.path:
        sys.path.insert(0, p)
