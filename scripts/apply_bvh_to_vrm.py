#!/usr/bin/env python3
"""
BVH → VRM適用スクリプト

BlenderでBVHアニメーションをVRMモデルに適用し、動画をレンダリングする。

使用方法:
    blender --background --python apply_bvh_to_vrm.py -- \
        --vrm assets/character.vrm \
        --bvh output/radio_wham.bvh \
        --output output/radio_vrm_final.mp4

必要なBlenderアドオン:
    - VRM Add-on for Blender (https://vrm-addon-for-blender.info/)
"""

import sys
import argparse
from pathlib import Path
from typing import Optional, Tuple


def check_blender_environment():
    """Blender環境かどうかを確認"""
    try:
        import bpy
        return True
    except ImportError:
        return False


# Blender環境の場合のみインポート
if check_blender_environment():
    import bpy
    import mathutils


# SMPL関節名からVRM Humanoid Bone名へのマッピング
SMPL_TO_VRM_BONE_MAP = {
    "Pelvis": "hips",
    "Spine1": "spine",
    "Spine2": "chest",
    "Spine3": "upperChest",
    "Neck": "neck",
    "Head": "head",
    "L_Hip": "leftUpperLeg",
    "R_Hip": "rightUpperLeg",
    "L_Knee": "leftLowerLeg",
    "R_Knee": "rightLowerLeg",
    "L_Ankle": "leftFoot",
    "R_Ankle": "rightFoot",
    "L_Foot": "leftToes",
    "R_Foot": "rightToes",
    "L_Collar": "leftShoulder",
    "R_Collar": "rightShoulder",
    "L_Shoulder": "leftUpperArm",
    "R_Shoulder": "rightUpperArm",
    "L_Elbow": "leftLowerArm",
    "R_Elbow": "rightLowerArm",
    "L_Wrist": "leftHand",
    "R_Wrist": "rightHand",
    "L_Hand": "leftHand",  # VRMには手のボーンがない場合がある
    "R_Hand": "rightHand",
}

# VRM BVHボーン名（J_Bip_*）からVRM Humanoid Bone名へのマッピング
VRM_BVH_TO_VRM_BONE_MAP = {
    "J_Bip_C_Hips": "hips",
    "J_Bip_C_Spine": "spine",
    "J_Bip_C_Chest": "chest",
    "J_Bip_C_UpperChest": "upperChest",
    "J_Bip_C_Neck": "neck",
    "J_Bip_C_Head": "head",
    "J_Bip_L_Shoulder": "leftShoulder",
    "J_Bip_R_Shoulder": "rightShoulder",
    "J_Bip_L_UpperArm": "leftUpperArm",
    "J_Bip_R_UpperArm": "rightUpperArm",
    "J_Bip_L_LowerArm": "leftLowerArm",
    "J_Bip_R_LowerArm": "rightLowerArm",
    "J_Bip_L_Hand": "leftHand",
    "J_Bip_R_Hand": "rightHand",
    "J_Bip_L_UpperLeg": "leftUpperLeg",
    "J_Bip_R_UpperLeg": "rightUpperLeg",
    "J_Bip_L_LowerLeg": "leftLowerLeg",
    "J_Bip_R_LowerLeg": "rightLowerLeg",
    "J_Bip_L_Foot": "leftFoot",
    "J_Bip_R_Foot": "rightFoot",
}


def import_vrm(vrm_path: str) -> Optional[object]:
    """
    VRMファイルをインポート

    Args:
        vrm_path: VRMファイルのパス

    Returns:
        インポートされたアーマチュアオブジェクト
    """
    if not check_blender_environment():
        return None

    vrm_path = Path(vrm_path)
    if not vrm_path.exists():
        raise FileNotFoundError(f"VRMファイルが見つかりません: {vrm_path}")

    # VRMアドオンがインストールされているか確認
    try:
        bpy.ops.import_scene.vrm(filepath=str(vrm_path))
    except AttributeError:
        # VRMアドオンがない場合、GLBとしてインポートを試みる
        print("警告: VRMアドオンが見つかりません。GLBとしてインポートを試みます。")
        bpy.ops.import_scene.gltf(filepath=str(vrm_path))

    # アーマチュアを探す
    for obj in bpy.context.selected_objects:
        if obj.type == 'ARMATURE':
            return obj

    # 選択されていない場合、シーンから探す
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            return obj

    return None


def import_bvh(bvh_path: str, scale: float = 0.01) -> Optional[object]:
    """
    BVHファイルをインポート

    Args:
        bvh_path: BVHファイルのパス
        scale: スケール（BVHはcm単位、Blenderはm単位が一般的）

    Returns:
        インポートされたアーマチュアオブジェクト
    """
    if not check_blender_environment():
        return None

    bvh_path = Path(bvh_path)
    if not bvh_path.exists():
        raise FileNotFoundError(f"BVHファイルが見つかりません: {bvh_path}")

    bpy.ops.import_anim.bvh(
        filepath=str(bvh_path),
        filter_glob="*.bvh",
        target='ARMATURE',
        global_scale=scale,
        frame_start=1,
        use_fps_scale=True,
        update_scene_fps=False,
        update_scene_duration=True,
        use_cyclic=False,
        rotate_mode='NATIVE'
    )

    # インポートされたアーマチュアを取得
    for obj in bpy.context.selected_objects:
        if obj.type == 'ARMATURE':
            return obj

    return None


def apply_animation(vrm_armature: object, bvh_armature: object) -> bool:
    """
    BVHアニメーションをVRMアーマチュアに適用

    Args:
        vrm_armature: VRMのアーマチュアオブジェクト
        bvh_armature: BVHのアーマチュアオブジェクト

    Returns:
        成功したかどうか
    """
    if not check_blender_environment():
        return False

    if vrm_armature is None or bvh_armature is None:
        print("エラー: アーマチュアが見つかりません")
        return False

    # BVHのアニメーションデータを取得
    if bvh_armature.animation_data is None or bvh_armature.animation_data.action is None:
        print("エラー: BVHにアニメーションデータがありません")
        return False

    bvh_action = bvh_armature.animation_data.action

    # フレーム範囲を設定
    frame_start = int(bvh_action.frame_range[0])
    frame_end = int(bvh_action.frame_range[1])

    bpy.context.scene.frame_start = frame_start
    bpy.context.scene.frame_end = frame_end

    # VRMアーマチュアにアニメーションデータを作成
    if vrm_armature.animation_data is None:
        vrm_armature.animation_data_create()

    vrm_armature.animation_data.action = bpy.data.actions.new(name="VRM_Animation")
    vrm_action = vrm_armature.animation_data.action

    # BVHボーンからVRMボーンへの回転をコピー
    bvh_pose_bones = bvh_armature.pose.bones
    vrm_pose_bones = vrm_armature.pose.bones

    # ボーンマッピングを作成（SMPLとVRM両方のBVH形式に対応）
    bone_mapping = {}
    for bvh_bone in bvh_pose_bones:
        # VRM BVHボーン名（J_Bip_*形式）を優先
        vrm_bone_name = VRM_BVH_TO_VRM_BONE_MAP.get(bvh_bone.name)
        # 見つからなければSMPL形式を試す
        if vrm_bone_name is None:
            vrm_bone_name = SMPL_TO_VRM_BONE_MAP.get(bvh_bone.name)
        if vrm_bone_name:
            for vrm_bone in vrm_pose_bones:
                if vrm_bone_name.lower() in vrm_bone.name.lower():
                    bone_mapping[bvh_bone.name] = vrm_bone.name
                    break

    print(f"ボーンマッピング: {len(bone_mapping)}個のボーンをマッピング")

    # 各フレームでアニメーションをコピー
    for frame in range(frame_start, frame_end + 1):
        bpy.context.scene.frame_set(frame)

        for bvh_name, vrm_name in bone_mapping.items():
            bvh_bone = bvh_pose_bones.get(bvh_name)
            vrm_bone = vrm_pose_bones.get(vrm_name)

            if bvh_bone and vrm_bone:
                # 回転をコピー
                vrm_bone.rotation_mode = 'QUATERNION'
                vrm_bone.rotation_quaternion = bvh_bone.rotation_quaternion.copy()
                vrm_bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)

        # ルート位置もコピー（Hips）
        # VRM BVH（J_Bip_C_Hips）とSMPL（Pelvis）両方をサポート
        bvh_root = bvh_pose_bones.get("J_Bip_C_Hips") or bvh_pose_bones.get("Pelvis")
        vrm_root = None
        for bone in vrm_pose_bones:
            if "hips" in bone.name.lower():
                vrm_root = bone
                break

        if bvh_root and vrm_root:
            vrm_root.location = bvh_root.location.copy()
            vrm_root.keyframe_insert(data_path="location", frame=frame)

    print(f"アニメーション適用完了: {frame_end - frame_start + 1}フレーム")
    return True


def render_animation(
    output_path: str,
    resolution: Tuple[int, int] = (1280, 720),
    fps: int = 30
) -> bool:
    """
    アニメーションを動画としてレンダリング

    Args:
        output_path: 出力動画のパス
        resolution: 解像度 (width, height)
        fps: フレームレート

    Returns:
        成功したかどうか
    """
    if not check_blender_environment():
        return False

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    scene = bpy.context.scene

    # レンダリング設定
    scene.render.resolution_x = resolution[0]
    scene.render.resolution_y = resolution[1]
    scene.render.resolution_percentage = 100
    scene.render.fps = fps

    # 出力形式
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'
    scene.render.filepath = str(output_path.with_suffix(''))

    # レンダリングエンジン
    scene.render.engine = 'BLENDER_EEVEE'

    # カメラが存在しない場合は作成
    if not any(obj.type == 'CAMERA' for obj in bpy.data.objects):
        bpy.ops.object.camera_add(location=(0, -3, 1.5))
        camera = bpy.context.object
        camera.rotation_euler = (1.5708, 0, 0)  # 90度回転
        scene.camera = camera

    # ライトが存在しない場合は作成
    if not any(obj.type == 'LIGHT' for obj in bpy.data.objects):
        bpy.ops.object.light_add(type='SUN', location=(0, 0, 5))

    # アニメーションをレンダリング
    print(f"レンダリング開始: {scene.frame_start} - {scene.frame_end}")
    bpy.ops.render.render(animation=True)

    print(f"レンダリング完了: {output_path}")
    return True


def setup_scene():
    """シーンを初期化"""
    if not check_blender_environment():
        return

    # デフォルトオブジェクトを削除
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # ワールド背景を設定
    world = bpy.data.worlds.get("World")
    if world:
        world.color = (0.2, 0.2, 0.2)


def main():
    """メインエントリーポイント"""
    # Blenderから実行された場合、'--'以降の引数を取得
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="BVH → VRM適用スクリプト")
    parser.add_argument("--vrm", required=True, help="VRMファイルのパス")
    parser.add_argument("--bvh", required=True, help="BVHファイルのパス")
    parser.add_argument("--output", required=True, help="出力動画のパス")
    parser.add_argument("--width", type=int, default=1280, help="出力幅")
    parser.add_argument("--height", type=int, default=720, help="出力高さ")
    parser.add_argument("--fps", type=int, default=30, help="フレームレート")

    args = parser.parse_args(argv)

    if not check_blender_environment():
        print("エラー: このスクリプトはBlender内で実行する必要があります")
        print("使用方法: blender --background --python apply_bvh_to_vrm.py -- --vrm <VRM> --bvh <BVH> --output <OUTPUT>")
        sys.exit(1)

    # シーンを初期化
    setup_scene()

    # VRMをインポート
    print(f"VRMをインポート: {args.vrm}")
    vrm_armature = import_vrm(args.vrm)
    if vrm_armature is None:
        print("エラー: VRMのインポートに失敗しました")
        sys.exit(1)

    # BVHをインポート
    print(f"BVHをインポート: {args.bvh}")
    bvh_armature = import_bvh(args.bvh)
    if bvh_armature is None:
        print("エラー: BVHのインポートに失敗しました")
        sys.exit(1)

    # アニメーションを適用
    print("アニメーションを適用中...")
    if not apply_animation(vrm_armature, bvh_armature):
        print("エラー: アニメーションの適用に失敗しました")
        sys.exit(1)

    # BVHアーマチュアを非表示にする
    bvh_armature.hide_viewport = True
    bvh_armature.hide_render = True

    # レンダリング
    print(f"レンダリング開始: {args.output}")
    if not render_animation(args.output, (args.width, args.height), args.fps):
        print("エラー: レンダリングに失敗しました")
        sys.exit(1)

    print("処理完了!")


if __name__ == "__main__":
    main()
