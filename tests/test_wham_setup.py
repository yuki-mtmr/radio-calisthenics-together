"""
WHAMセットアップの検証テスト

TDD: このテストは環境構築前に失敗し、構築後に成功する
"""

import os
import subprocess
import sys
from pathlib import Path
import pytest


PROJECT_ROOT = Path(__file__).parent.parent


class TestWhamEnvironment:
    """WHAM環境構築の検証"""

    def test_wham_directory_exists(self):
        """WHAMディレクトリが存在すること"""
        wham_dir = PROJECT_ROOT / "WHAM"
        assert wham_dir.exists(), "WHAMディレクトリが存在しません"

    def test_wham_demo_script_exists(self):
        """WHAMのdemo.pyが存在すること"""
        demo_script = PROJECT_ROOT / "WHAM" / "demo.py"
        assert demo_script.exists(), "WHAM/demo.py が存在しません"

    def test_smpl2bvh_directory_exists(self):
        """smpl2bvhディレクトリが存在すること"""
        smpl2bvh_dir = PROJECT_ROOT / "smpl2bvh"
        assert smpl2bvh_dir.exists(), "smpl2bvhディレクトリが存在しません"

    def test_smpl2bvh_script_exists(self):
        """smpl2bvh変換スクリプトが存在すること"""
        script = PROJECT_ROOT / "smpl2bvh" / "smpl2bvh.py"
        assert script.exists(), "smpl2bvh/smpl2bvh.py が存在しません"


class TestInputFiles:
    """入力ファイルの検証"""

    def test_input_video_exists(self):
        """入力動画が存在すること"""
        video = PROJECT_ROOT / "output" / "radio_right_person.mp4"
        assert video.exists(), "入力動画 output/radio_right_person.mp4 が存在しません"

    def test_vrm_model_exists(self):
        """VRMモデルが存在すること"""
        vrm = PROJECT_ROOT / "assets" / "character.vrm"
        assert vrm.exists(), "VRMモデル assets/character.vrm が存在しません"

    def test_input_video_is_reasonable_size(self):
        """入力動画が適切なサイズであること"""
        video = PROJECT_ROOT / "output" / "radio_right_person.mp4"
        if video.exists():
            size_mb = video.stat().st_size / (1024 * 1024)
            assert size_mb > 1, f"動画サイズが小さすぎます: {size_mb:.2f}MB"
            assert size_mb < 500, f"動画サイズが大きすぎます: {size_mb:.2f}MB"


class TestBlenderAvailable:
    """Blenderの利用可能性"""

    def test_blender_exists(self):
        """Blenderがインストールされていること"""
        blender_path = Path("/Applications/Blender.app/Contents/MacOS/Blender")
        assert blender_path.exists(), "Blenderがインストールされていません"

    @pytest.mark.slow
    def test_blender_can_run(self):
        """Blenderが実行可能であること（時間がかかるテスト）"""
        blender_path = "/Applications/Blender.app/Contents/MacOS/Blender"
        # -b (background) と --version でGUI起動を防ぐ
        result = subprocess.run(
            [blender_path, "-b", "--version"],
            capture_output=True,
            text=True,
            timeout=60  # タイムアウトを延長
        )
        assert result.returncode == 0, f"Blender実行エラー: {result.stderr}"
        assert "Blender" in result.stdout, "Blenderのバージョン情報が取得できません"
