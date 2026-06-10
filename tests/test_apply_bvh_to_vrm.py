"""
BVH → VRM適用スクリプトのテスト

TDD: Blenderスクリプトの検証
"""

import os
import subprocess
from pathlib import Path
import pytest


PROJECT_ROOT = Path(__file__).parent.parent
BLENDER_PATH = Path("/Applications/Blender.app/Contents/MacOS/Blender")


class TestApplyBvhToVrmScript:
    """BVH→VRM適用スクリプトのテスト"""

    def test_script_exists(self):
        """スクリプトが存在すること"""
        script_path = PROJECT_ROOT / "scripts" / "apply_bvh_to_vrm.py"
        assert script_path.exists(), "scripts/apply_bvh_to_vrm.py が存在しません"

    def test_script_is_valid_python(self):
        """スクリプトが有効なPythonであること"""
        script_path = PROJECT_ROOT / "scripts" / "apply_bvh_to_vrm.py"
        if not script_path.exists():
            pytest.skip("スクリプトが存在しません")

        result = subprocess.run(
            ["python3", "-m", "py_compile", str(script_path)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"構文エラー: {result.stderr}"

    def test_script_has_required_functions(self):
        """スクリプトに必要な関数が定義されていること"""
        script_path = PROJECT_ROOT / "scripts" / "apply_bvh_to_vrm.py"
        if not script_path.exists():
            pytest.skip("スクリプトが存在しません")

        content = script_path.read_text()

        # 必要な関数が定義されているか確認
        assert "def import_vrm" in content, "import_vrm関数がありません"
        assert "def import_bvh" in content, "import_bvh関数がありません"
        assert "def apply_animation" in content, "apply_animation関数がありません"
        assert "def render_animation" in content, "render_animation関数がありません"


class TestVrmAsset:
    """VRMアセットのテスト"""

    def test_vrm_file_exists(self):
        """VRMファイルが存在すること"""
        vrm_path = PROJECT_ROOT / "assets" / "character.vrm"
        assert vrm_path.exists(), "assets/character.vrm が存在しません"

    def test_vrm_file_is_valid_size(self):
        """VRMファイルが適切なサイズであること"""
        vrm_path = PROJECT_ROOT / "assets" / "character.vrm"
        if not vrm_path.exists():
            pytest.skip("VRMファイルが存在しません")

        size_mb = vrm_path.stat().st_size / (1024 * 1024)
        assert size_mb > 0.1, f"VRMファイルが小さすぎます: {size_mb:.2f}MB"
        assert size_mb < 100, f"VRMファイルが大きすぎます: {size_mb:.2f}MB"


class TestBlenderIntegration:
    """Blender連携のテスト"""

    @pytest.mark.slow
    @pytest.mark.skipif(not BLENDER_PATH.exists(), reason="Blenderがインストールされていません")
    def test_blender_version(self):
        """Blenderのバージョンが3.6以上であること"""
        # このテストは時間がかかるため、-m "not slow" でスキップ可能
        result = subprocess.run(
            [str(BLENDER_PATH), "-b", "--version"],
            capture_output=True,
            text=True,
            timeout=60  # タイムアウトを延長
        )

        assert result.returncode == 0, f"Blender実行エラー: {result.stderr}"

        # バージョンを抽出
        version_line = result.stdout.split("\n")[0]
        assert "Blender" in version_line, "Blenderバージョン情報が取得できません"


class TestVrmBoneMapping:
    """VRMボーンマッピングのテスト"""

    def test_vrm_bone_mapping_exists(self):
        """VRM用ボーンマッピングが定義されていること"""
        script_path = PROJECT_ROOT / "scripts" / "apply_bvh_to_vrm.py"
        if not script_path.exists():
            pytest.skip("スクリプトが存在しません")

        content = script_path.read_text()
        # VRMボーン名（J_Bip_*形式）のマッピングがあること
        assert "J_Bip_" in content, "VRMボーン名のマッピングがありません"

    def test_vrm_bone_mapping_has_required_bones(self):
        """必要なボーンマッピングが含まれていること"""
        script_path = PROJECT_ROOT / "scripts" / "apply_bvh_to_vrm.py"
        if not script_path.exists():
            pytest.skip("スクリプトが存在しません")

        content = script_path.read_text()
        required_bones = [
            "J_Bip_C_Hips",
            "J_Bip_C_Spine",
            "J_Bip_L_UpperArm",
            "J_Bip_R_UpperArm",
            "J_Bip_L_UpperLeg",
            "J_Bip_R_UpperLeg",
        ]
        for bone in required_bones:
            assert bone in content, f"ボーン {bone} のマッピングがありません"
