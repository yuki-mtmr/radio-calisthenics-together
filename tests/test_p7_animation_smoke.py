"""P7 アニメ系スモークテスト (_check_media_head のみ)。

full_body_v3 のテストは生成系の分離に伴い radio-calisthenics-studio へ移設した
(tests/test_full_body_smoke.py)。
"""
import ast
import os
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / "scripts"


def _has_no_toplevel_mediapipe(path: Path) -> bool:
    """モジュールレベルで mediapipe / cv2 を import しないことを AST で確認する。"""
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            else:
                names = [node.module or ""]
            if any(n.startswith(("mediapipe", "cv2")) for n in names):
                # 関数/クラス内部ならOK
                return False
    return True


def test_check_media_head_exists():
    assert (SCRIPTS / "_check_media_head.py").exists()


def test_check_media_head_no_toplevel_mediapipe():
    """_check_media_head は mediapipe を使わない (rct.obs_client のみ依存)。"""
    assert _has_no_toplevel_mediapipe(SCRIPTS / "_check_media_head.py")
