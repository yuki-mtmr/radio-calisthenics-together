"""
SMPL → BVH変換スクリプトのテスト

TDD: 変換スクリプトの検証
"""

import os
import sys
from pathlib import Path
import pytest
import numpy as np


PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


class TestSmplToBvhConverter:
    """SMPL→BVH変換のテスト"""

    def test_converter_module_exists(self):
        """変換モジュールが存在すること"""
        converter_path = PROJECT_ROOT / "scripts" / "smpl_to_bvh_converter.py"
        assert converter_path.exists(), "scripts/smpl_to_bvh_converter.py が存在しません"

    def test_can_import_converter(self):
        """変換モジュールがインポートできること"""
        try:
            from smpl_to_bvh_converter import SmplToBvhConverter
        except ImportError as e:
            pytest.fail(f"モジュールのインポートに失敗: {e}")

    def test_converter_has_convert_method(self):
        """変換メソッドが存在すること"""
        from smpl_to_bvh_converter import SmplToBvhConverter
        converter = SmplToBvhConverter()
        assert hasattr(converter, 'convert'), "convertメソッドが存在しません"

    def test_convert_raises_on_missing_file(self):
        """存在しないファイルでエラーになること"""
        from smpl_to_bvh_converter import SmplToBvhConverter
        converter = SmplToBvhConverter()
        with pytest.raises(FileNotFoundError):
            converter.convert("nonexistent.pkl", "output.bvh")


class TestSmplDataParser:
    """SMPLデータのパースのテスト"""

    def test_parse_smpl_poses(self):
        """SMPLのposesパラメータをパースできること"""
        from smpl_to_bvh_converter import SmplToBvhConverter
        converter = SmplToBvhConverter()

        # テスト用のダミーデータ（10フレーム、24関節 × 3軸 = 72次元）
        dummy_poses = np.zeros((10, 72))

        # パースできることを確認
        result = converter.parse_poses(dummy_poses)
        assert result is not None
        assert len(result) == 10, "フレーム数が正しくありません"

    def test_parse_smpl_betas(self):
        """SMPLのbetasパラメータをパースできること"""
        from smpl_to_bvh_converter import SmplToBvhConverter
        converter = SmplToBvhConverter()

        # テスト用のダミーデータ（10次元の形状パラメータ）
        dummy_betas = np.zeros(10)

        result = converter.parse_betas(dummy_betas)
        assert result is not None


class TestBvhOutput:
    """BVH出力のテスト"""

    def test_generate_bvh_header(self):
        """BVHヘッダーを生成できること"""
        from smpl_to_bvh_converter import SmplToBvhConverter
        converter = SmplToBvhConverter()

        header = converter.generate_bvh_header()
        assert "HIERARCHY" in header, "HIERARCHYセクションがありません"
        assert "ROOT" in header, "ROOTがありません"

    def test_generate_bvh_motion(self):
        """BVHモーションデータを生成できること"""
        from smpl_to_bvh_converter import SmplToBvhConverter
        converter = SmplToBvhConverter()

        # ダミーデータ
        dummy_poses = np.zeros((10, 72))

        motion = converter.generate_bvh_motion(dummy_poses, fps=30)
        assert "MOTION" in motion, "MOTIONセクションがありません"
        assert "Frames: 10" in motion, "フレーム数が正しくありません"
        assert "Frame Time:" in motion, "Frame Timeがありません"
