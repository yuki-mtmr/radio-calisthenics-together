#!/usr/bin/env python3
"""
SMPL → BVH変換スクリプト

WHAMの出力（SMPLパラメータ）をBVH形式に変換する。

使用方法:
    python smpl_to_bvh_converter.py --input wham_output.pkl --output output.bvh
"""

import argparse
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


# SMPL関節の階層構造（24関節）
SMPL_JOINT_NAMES = [
    "Pelvis",           # 0
    "L_Hip",            # 1
    "R_Hip",            # 2
    "Spine1",           # 3
    "L_Knee",           # 4
    "R_Knee",           # 5
    "Spine2",           # 6
    "L_Ankle",          # 7
    "R_Ankle",          # 8
    "Spine3",           # 9
    "L_Foot",           # 10
    "R_Foot",           # 11
    "Neck",             # 12
    "L_Collar",         # 13
    "R_Collar",         # 14
    "Head",             # 15
    "L_Shoulder",       # 16
    "R_Shoulder",       # 17
    "L_Elbow",          # 18
    "R_Elbow",          # 19
    "L_Wrist",          # 20
    "R_Wrist",          # 21
    "L_Hand",           # 22
    "R_Hand",           # 23
]

# SMPL関節の親子関係
SMPL_PARENT = {
    0: -1,   # Pelvis (root)
    1: 0,    # L_Hip -> Pelvis
    2: 0,    # R_Hip -> Pelvis
    3: 0,    # Spine1 -> Pelvis
    4: 1,    # L_Knee -> L_Hip
    5: 2,    # R_Knee -> R_Hip
    6: 3,    # Spine2 -> Spine1
    7: 4,    # L_Ankle -> L_Knee
    8: 5,    # R_Ankle -> R_Knee
    9: 6,    # Spine3 -> Spine2
    10: 7,   # L_Foot -> L_Ankle
    11: 8,   # R_Foot -> R_Ankle
    12: 9,   # Neck -> Spine3
    13: 9,   # L_Collar -> Spine3
    14: 9,   # R_Collar -> Spine3
    15: 12,  # Head -> Neck
    16: 13,  # L_Shoulder -> L_Collar
    17: 14,  # R_Shoulder -> R_Collar
    18: 16,  # L_Elbow -> L_Shoulder
    19: 17,  # R_Elbow -> R_Shoulder
    20: 18,  # L_Wrist -> L_Elbow
    21: 19,  # R_Wrist -> R_Elbow
    22: 20,  # L_Hand -> L_Wrist
    23: 21,  # R_Hand -> R_Wrist
}

# T-Poseでの関節オフセット（おおよその値、実際はSMPLモデルから取得）
SMPL_OFFSETS = {
    0: (0, 0, 0),
    1: (0.1, -0.1, 0),
    2: (-0.1, -0.1, 0),
    3: (0, 0.1, 0),
    4: (0, -0.4, 0),
    5: (0, -0.4, 0),
    6: (0, 0.1, 0),
    7: (0, -0.4, 0),
    8: (0, -0.4, 0),
    9: (0, 0.1, 0),
    10: (0, -0.05, 0.1),
    11: (0, -0.05, 0.1),
    12: (0, 0.1, 0),
    13: (0.05, 0.05, 0),
    14: (-0.05, 0.05, 0),
    15: (0, 0.1, 0),
    16: (0.1, 0, 0),
    17: (-0.1, 0, 0),
    18: (0.25, 0, 0),
    19: (-0.25, 0, 0),
    20: (0.25, 0, 0),
    21: (-0.25, 0, 0),
    22: (0.1, 0, 0),
    23: (-0.1, 0, 0),
}


def rodrigues_to_euler(rvec: np.ndarray) -> np.ndarray:
    """
    Rodrigues回転ベクトルをオイラー角（XYZ順）に変換

    Args:
        rvec: Rodrigues回転ベクトル (3,)

    Returns:
        オイラー角 (rx, ry, rz) in degrees
    """
    theta = np.linalg.norm(rvec)
    if theta < 1e-8:
        return np.zeros(3)

    # 回転軸
    axis = rvec / theta

    # 回転行列を構築
    K = np.array([
        [0, -axis[2], axis[1]],
        [axis[2], 0, -axis[0]],
        [-axis[1], axis[0], 0]
    ])
    R = np.eye(3) + np.sin(theta) * K + (1 - np.cos(theta)) * K @ K

    # 回転行列からオイラー角を抽出（XYZ順）
    sy = np.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)

    if sy > 1e-6:
        rx = np.arctan2(R[2, 1], R[2, 2])
        ry = np.arctan2(-R[2, 0], sy)
        rz = np.arctan2(R[1, 0], R[0, 0])
    else:
        rx = np.arctan2(-R[1, 2], R[1, 1])
        ry = np.arctan2(-R[2, 0], sy)
        rz = 0

    return np.degrees(np.array([rx, ry, rz]))


class SmplToBvhConverter:
    """SMPL → BVH変換クラス"""

    def __init__(self, scale: float = 100.0):
        """
        Args:
            scale: BVH出力のスケール（SMPLはメートル単位、BVHはcm単位が一般的）
        """
        self.scale = scale

    def convert(self, input_path: str, output_path: str, fps: float = 30.0) -> None:
        """
        SMPLパラメータファイルをBVHに変換

        Args:
            input_path: 入力ファイルパス（.pkl or .npz）
            output_path: 出力BVHファイルパス
            fps: フレームレート

        Raises:
            FileNotFoundError: 入力ファイルが存在しない場合
        """
        input_file = Path(input_path)
        if not input_file.exists():
            raise FileNotFoundError(f"入力ファイルが存在しません: {input_path}")

        # データを読み込み
        data = self._load_smpl_data(input_path)

        poses = data.get("poses", data.get("body_pose", None))
        trans = data.get("trans", data.get("global_trans", np.zeros((len(poses), 3))))

        if poses is None:
            raise ValueError("SMPLデータにposesが含まれていません")

        # BVHを生成
        bvh_content = self._generate_bvh(poses, trans, fps)

        # ファイルに書き込み
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(bvh_content)

        print(f"BVHファイルを出力しました: {output_path}")

    def _load_smpl_data(self, path: str) -> Dict:
        """SMPLデータを読み込む"""
        path = Path(path)

        if path.suffix == ".pkl":
            with open(path, "rb") as f:
                return pickle.load(f)
        elif path.suffix == ".npz":
            data = np.load(path, allow_pickle=True)
            return {k: data[k] for k in data.files}
        else:
            raise ValueError(f"未サポートのファイル形式: {path.suffix}")

    def parse_poses(self, poses: np.ndarray) -> List[np.ndarray]:
        """
        SMPLのposesパラメータをパース

        Args:
            poses: (num_frames, 72) または (num_frames, 24, 3)

        Returns:
            各フレームの関節回転リスト
        """
        if poses.ndim == 2 and poses.shape[1] == 72:
            # (num_frames, 72) -> (num_frames, 24, 3)
            poses = poses.reshape(-1, 24, 3)

        return [poses[i] for i in range(len(poses))]

    def parse_betas(self, betas: np.ndarray) -> np.ndarray:
        """
        SMPLのbetasパラメータをパース

        Args:
            betas: 形状パラメータ (10,)

        Returns:
            形状パラメータ
        """
        return betas

    def generate_bvh_header(self) -> str:
        """BVHのHIERARCHYセクションを生成"""
        lines = ["HIERARCHY"]
        self._write_joint(lines, 0, 0)
        return "\n".join(lines)

    def _write_joint(self, lines: List[str], joint_idx: int, depth: int) -> None:
        """再帰的に関節を書き込む"""
        indent = "  " * depth
        joint_name = SMPL_JOINT_NAMES[joint_idx]
        offset = SMPL_OFFSETS[joint_idx]
        offset_scaled = tuple(v * self.scale for v in offset)

        if joint_idx == 0:
            lines.append(f"{indent}ROOT {joint_name}")
        else:
            lines.append(f"{indent}JOINT {joint_name}")

        lines.append(f"{indent}{{")
        lines.append(f"{indent}  OFFSET {offset_scaled[0]:.6f} {offset_scaled[1]:.6f} {offset_scaled[2]:.6f}")

        if joint_idx == 0:
            lines.append(f"{indent}  CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation")
        else:
            lines.append(f"{indent}  CHANNELS 3 Zrotation Xrotation Yrotation")

        # 子関節を探す
        children = [j for j, p in SMPL_PARENT.items() if p == joint_idx]

        if children:
            for child in children:
                self._write_joint(lines, child, depth + 1)
        else:
            # End Site
            lines.append(f"{indent}  End Site")
            lines.append(f"{indent}  {{")
            lines.append(f"{indent}    OFFSET 0.000000 0.000000 0.000000")
            lines.append(f"{indent}  }}")

        lines.append(f"{indent}}}")

    def generate_bvh_motion(self, poses: np.ndarray, fps: float = 30.0, trans: Optional[np.ndarray] = None) -> str:
        """
        BVHのMOTIONセクションを生成

        Args:
            poses: (num_frames, 72) または (num_frames, 24, 3)
            fps: フレームレート
            trans: (num_frames, 3) ルート位置

        Returns:
            MOTIONセクションの文字列
        """
        parsed_poses = self.parse_poses(poses)
        num_frames = len(parsed_poses)
        frame_time = 1.0 / fps

        lines = ["MOTION"]
        lines.append(f"Frames: {num_frames}")
        lines.append(f"Frame Time: {frame_time:.6f}")

        if trans is None:
            trans = np.zeros((num_frames, 3))

        for frame_idx in range(num_frames):
            frame_data = []

            # ルート位置
            root_pos = trans[frame_idx] * self.scale
            frame_data.extend([f"{root_pos[0]:.6f}", f"{root_pos[1]:.6f}", f"{root_pos[2]:.6f}"])

            # 各関節の回転（BFS順）
            joint_order = self._get_joint_order()
            for joint_idx in joint_order:
                rvec = parsed_poses[frame_idx][joint_idx]
                euler = rodrigues_to_euler(rvec)
                # BVH形式はZXY順
                frame_data.extend([f"{euler[2]:.6f}", f"{euler[0]:.6f}", f"{euler[1]:.6f}"])

            lines.append(" ".join(frame_data))

        return "\n".join(lines)

    def _get_joint_order(self) -> List[int]:
        """BVHの関節順序を取得（BFS順）"""
        order = []
        queue = [0]

        while queue:
            current = queue.pop(0)
            order.append(current)
            children = [j for j, p in SMPL_PARENT.items() if p == current]
            queue.extend(children)

        return order

    def _generate_bvh(self, poses: np.ndarray, trans: np.ndarray, fps: float) -> str:
        """完全なBVHファイルを生成"""
        header = self.generate_bvh_header()
        motion = self.generate_bvh_motion(poses, fps, trans)
        return header + "\n" + motion


def main():
    """メインエントリーポイント"""
    parser = argparse.ArgumentParser(description="SMPL → BVH変換")
    parser.add_argument("--input", "-i", required=True, help="入力SMPLファイル（.pkl or .npz）")
    parser.add_argument("--output", "-o", required=True, help="出力BVHファイル")
    parser.add_argument("--fps", type=float, default=30.0, help="フレームレート（デフォルト: 30）")
    parser.add_argument("--scale", type=float, default=100.0, help="スケール（デフォルト: 100）")

    args = parser.parse_args()

    converter = SmplToBvhConverter(scale=args.scale)
    converter.convert(args.input, args.output, fps=args.fps)


if __name__ == "__main__":
    main()
