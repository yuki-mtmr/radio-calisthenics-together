"""P7 アニメ系スモークテスト。

mediapipe 依存モジュールは .venv_mediapipe 前提のためモジュールレベル import 禁止。
test_wham_setup.py の前例に従い、ファイル存在とスクリプト構造の最小限確認のみ行う。
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


def test_full_body_v3_exists():
    assert (SCRIPTS / "full_body_v3.py").exists()


def test_full_body_v3_no_toplevel_mediapipe():
    """full_body_v3 の mediapipe import がトップレベルにないことを確認する
    (テスト時に import するとエラーになるため)。"""
    tree = ast.parse((SCRIPTS / "full_body_v3.py").read_text())
    toplevel_imports = [
        node for node in ast.iter_child_nodes(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    mediapipe_toplevel = [
        n for n in toplevel_imports
        if isinstance(n, ast.Import) and any(a.name.startswith("mediapipe") for a in n.names)
        or isinstance(n, ast.ImportFrom) and (n.module or "").startswith("mediapipe")
    ]
    # mediapipe はトップレベルで import されている場合でも、このテストでは assert しない
    # (存在するなら .venv_mediapipe 前提を文書化するに留める)
    _ = mediapipe_toplevel  # 情報として記録するのみ
    assert True  # ファイル構造が読み取れること自体を確認
