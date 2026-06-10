"""
全身ポーズ抽出 v3 - 地面接地・正面向き修正
"""
import cv2
import mediapipe as mp
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.interpolate import interp1d
import sys
import time

class FullBodyPipelineV3:
    def __init__(self, sample_rate=2, smooth_sigma=2.0):
        self.sample_rate = sample_rate
        self.smooth_sigma = smooth_sigma

    def process_video(self, video_path, output_bvh, start_sec=0, end_sec=None):
        start_time = time.time()

        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps

        if end_sec is None:
            end_sec = duration

        start_frame = int(start_sec * fps)
        end_frame = min(int(end_sec * fps), total_frames)
        process_frames = end_frame - start_frame

        print(f"動画: {duration:.1f}秒, {fps:.1f}fps")
        print(f"処理範囲: {start_sec}秒 ~ {end_sec:.1f}秒")

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        # スティックマンで成功した設定を適用（高精度・スムージング有効）
        pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=2,           # 最高精度（スティックマン成功設定）
            enable_segmentation=True,     # セグメンテーション有効
            min_detection_confidence=0.5, # 検出閾値（緩めで見失いにくい）
            min_tracking_confidence=0.8,  # 追跡精度（高めでブレを抑える）
            smooth_landmarks=True         # スムージング有効
        )

        keyframes = []
        keyframe_indices = []
        frame_idx = 0

        print("抽出中...", end="", flush=True)

        while cap.get(cv2.CAP_PROP_POS_FRAMES) < end_frame:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % self.sample_rate == 0:
                results = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

                if results.pose_landmarks:
                    lm = results.pose_landmarks.landmark
                    angles = self._extract_angles(lm)
                    keyframes.append(angles)
                    keyframe_indices.append(frame_idx)
                elif keyframes:
                    keyframes.append(keyframes[-1].copy())
                    keyframe_indices.append(frame_idx)

            frame_idx += 1
            if frame_idx % 100 == 0:
                print(f"\r抽出中... {frame_idx * 100 // process_frames}%", end="", flush=True)

        cap.release()
        pose.close()

        print(f"\r抽出完了: {len(keyframes)}キーフレーム")

        if not keyframes:
            return None, 0

        smoothed = self._smooth_interpolate(keyframes, keyframe_indices, process_frames)
        self._write_bvh(smoothed, process_frames, fps, output_bvh)

        print(f"処理時間: {time.time() - start_time:.1f}秒")
        print(f"出力: {output_bvh}")
        return output_bvh, process_frames

    def _get_pos(self, lm, idx):
        """MediaPipe座標を取得（正規化座標）"""
        return np.array([
            lm[idx].x - 0.5,      # X: 右が正
            -(lm[idx].y - 0.5),   # Y: 上が正
            -lm[idx].z            # Z: 前が正
        ])

    def _extract_angles(self, lm):
        """関節角度を抽出"""
        # ランドマーク
        l_shoulder = self._get_pos(lm, 11)
        r_shoulder = self._get_pos(lm, 12)
        l_elbow = self._get_pos(lm, 13)
        r_elbow = self._get_pos(lm, 14)
        l_wrist = self._get_pos(lm, 15)
        r_wrist = self._get_pos(lm, 16)
        l_hip = self._get_pos(lm, 23)
        r_hip = self._get_pos(lm, 24)
        l_knee = self._get_pos(lm, 25)
        r_knee = self._get_pos(lm, 26)
        l_ankle = self._get_pos(lm, 27)
        r_ankle = self._get_pos(lm, 28)
        nose = self._get_pos(lm, 0)

        angles = {}

        # 体幹の傾き（小さい値のみ）
        shoulder_center = (l_shoulder + r_shoulder) / 2
        hip_center = (l_hip + r_hip) / 2
        spine = shoulder_center - hip_center
        spine = spine / (np.linalg.norm(spine) + 1e-6)

        angles['spine_x'] = np.degrees(np.arcsin(np.clip(spine[2], -0.3, 0.3))) * 0.5
        angles['spine_z'] = np.degrees(np.arcsin(np.clip(spine[0], -0.3, 0.3))) * 0.3

        # 頭
        head = nose - shoulder_center
        head = head / (np.linalg.norm(head) + 1e-6)
        angles['head_x'] = np.degrees(np.arcsin(np.clip(head[2], -0.5, 0.5))) * 0.5
        angles['head_z'] = np.degrees(np.arcsin(np.clip(head[0], -0.5, 0.5))) * 0.3

        # === 左腕 ===
        l_upper = l_elbow - l_shoulder
        l_lower = l_wrist - l_elbow

        # 肩を基準とした腕の角度
        l_upper_n = l_upper / (np.linalg.norm(l_upper) + 1e-6)

        # Z回転: 腕を上下（-90が下、0が横、90が上）
        # 左腕は左方向(+X)が基準
        angles['l_arm_z'] = np.degrees(np.arctan2(l_upper_n[1], l_upper_n[0]))

        # X回転: 腕を前後
        angles['l_arm_x'] = np.degrees(np.arcsin(np.clip(l_upper_n[2], -1, 1)))

        # 肘の曲げ
        l_lower_n = l_lower / (np.linalg.norm(l_lower) + 1e-6)
        dot = np.clip(np.dot(l_upper_n, l_lower_n), -1, 1)
        angles['l_elbow'] = -(180 - np.degrees(np.arccos(dot)))

        # === 右腕 ===
        r_upper = r_elbow - r_shoulder
        r_lower = r_wrist - r_elbow

        r_upper_n = r_upper / (np.linalg.norm(r_upper) + 1e-6)

        # Z回転: 右腕は右方向(-X)が基準なので符号反転
        angles['r_arm_z'] = -np.degrees(np.arctan2(r_upper_n[1], -r_upper_n[0]))

        # X回転
        angles['r_arm_x'] = np.degrees(np.arcsin(np.clip(r_upper_n[2], -1, 1)))

        # 肘
        r_lower_n = r_lower / (np.linalg.norm(r_lower) + 1e-6)
        dot = np.clip(np.dot(r_upper_n, r_lower_n), -1, 1)
        angles['r_elbow'] = -(180 - np.degrees(np.arccos(dot)))

        # === 左脚 ===
        l_thigh = l_knee - l_hip
        l_shin = l_ankle - l_knee

        l_thigh_n = l_thigh / (np.linalg.norm(l_thigh) + 1e-6)

        # 脚は下方向(-Y)が基準
        # X回転: 前に上げると正
        angles['l_leg_x'] = -np.degrees(np.arctan2(l_thigh_n[2], -l_thigh_n[1]))

        # Z回転: 横に開くと正（小さい値のみ）
        angles['l_leg_z'] = np.degrees(np.arcsin(np.clip(l_thigh_n[0], -0.3, 0.3))) * 0.5

        # 膝
        l_shin_n = l_shin / (np.linalg.norm(l_shin) + 1e-6)
        dot = np.clip(np.dot(l_thigh_n, l_shin_n), -1, 1)
        angles['l_knee'] = 180 - np.degrees(np.arccos(dot))

        # === 右脚 ===
        r_thigh = r_knee - r_hip
        r_shin = r_ankle - r_knee

        r_thigh_n = r_thigh / (np.linalg.norm(r_thigh) + 1e-6)

        angles['r_leg_x'] = -np.degrees(np.arctan2(r_thigh_n[2], -r_thigh_n[1]))
        angles['r_leg_z'] = -np.degrees(np.arcsin(np.clip(r_thigh_n[0], -0.3, 0.3))) * 0.5

        r_shin_n = r_shin / (np.linalg.norm(r_shin) + 1e-6)
        dot = np.clip(np.dot(r_thigh_n, r_shin_n), -1, 1)
        angles['r_knee'] = 180 - np.degrees(np.arccos(dot))

        return angles

    def _smooth_interpolate(self, keyframes, indices, total_frames):
        keys = list(keyframes[0].keys())
        data = {k: np.array([kf[k] for kf in keyframes]) for k in keys}

        for k in keys:
            if len(data[k]) > 3:
                data[k] = gaussian_filter1d(data[k], sigma=self.smooth_sigma)

        all_frames = np.arange(total_frames)
        result = {}

        for k in keys:
            if len(indices) >= 2:
                f = interp1d(indices, data[k], kind='cubic',
                           bounds_error=False, fill_value=(data[k][0], data[k][-1]))
                result[k] = f(all_frames)
            else:
                result[k] = np.full(total_frames, data[k][0])

        return result

    def _write_bvh(self, angles, total_frames, fps, output_path):
        header = '''HIERARCHY
ROOT J_Bip_C_Hips
{
  OFFSET 0.0 0.0 0.0
  CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation
  JOINT J_Bip_C_Spine
  {
    OFFSET 0.0 9.5 0.0
    CHANNELS 3 Zrotation Xrotation Yrotation
    JOINT J_Bip_C_Chest
    {
      OFFSET 0.0 11.0 0.0
      CHANNELS 3 Zrotation Xrotation Yrotation
      JOINT J_Bip_C_UpperChest
      {
        OFFSET 0.0 11.0 0.0
        CHANNELS 3 Zrotation Xrotation Yrotation
        JOINT J_Bip_C_Neck
        {
          OFFSET 0.0 8.0 0.0
          CHANNELS 3 Zrotation Xrotation Yrotation
          JOINT J_Bip_C_Head
          {
            OFFSET 0.0 10.0 0.0
            CHANNELS 3 Zrotation Xrotation Yrotation
            End Site
            {
              OFFSET 0.0 10.0 0.0
            }
          }
        }
        JOINT J_Bip_L_Shoulder
        {
          OFFSET 3.0 6.0 0.0
          CHANNELS 3 Zrotation Xrotation Yrotation
          JOINT J_Bip_L_UpperArm
          {
            OFFSET 8.0 0.0 0.0
            CHANNELS 3 Zrotation Xrotation Yrotation
            JOINT J_Bip_L_LowerArm
            {
              OFFSET 25.0 0.0 0.0
              CHANNELS 3 Zrotation Xrotation Yrotation
              JOINT J_Bip_L_Hand
              {
                OFFSET 22.0 0.0 0.0
                CHANNELS 3 Zrotation Xrotation Yrotation
                End Site
                {
                  OFFSET 8.0 0.0 0.0
                }
              }
            }
          }
        }
        JOINT J_Bip_R_Shoulder
        {
          OFFSET -3.0 6.0 0.0
          CHANNELS 3 Zrotation Xrotation Yrotation
          JOINT J_Bip_R_UpperArm
          {
            OFFSET -8.0 0.0 0.0
            CHANNELS 3 Zrotation Xrotation Yrotation
            JOINT J_Bip_R_LowerArm
            {
              OFFSET -25.0 0.0 0.0
              CHANNELS 3 Zrotation Xrotation Yrotation
              JOINT J_Bip_R_Hand
              {
                OFFSET -22.0 0.0 0.0
                CHANNELS 3 Zrotation Xrotation Yrotation
                End Site
                {
                  OFFSET -8.0 0.0 0.0
                }
              }
            }
          }
        }
      }
    }
  }
  JOINT J_Bip_L_UpperLeg
  {
    OFFSET 8.5 -2.0 0.0
    CHANNELS 3 Zrotation Xrotation Yrotation
    JOINT J_Bip_L_LowerLeg
    {
      OFFSET 0.0 -42.0 0.0
      CHANNELS 3 Zrotation Xrotation Yrotation
      JOINT J_Bip_L_Foot
      {
        OFFSET 0.0 -40.0 0.0
        CHANNELS 3 Zrotation Xrotation Yrotation
        End Site
        {
          OFFSET 0.0 -5.0 8.0
        }
      }
    }
  }
  JOINT J_Bip_R_UpperLeg
  {
    OFFSET -8.5 -2.0 0.0
    CHANNELS 3 Zrotation Xrotation Yrotation
    JOINT J_Bip_R_LowerLeg
    {
      OFFSET 0.0 -42.0 0.0
      CHANNELS 3 Zrotation Xrotation Yrotation
      JOINT J_Bip_R_Foot
      {
        OFFSET 0.0 -40.0 0.0
        CHANNELS 3 Zrotation Xrotation Yrotation
        End Site
        {
          OFFSET 0.0 -5.0 8.0
        }
      }
    }
  }
}
'''
        with open(output_path, 'w') as f:
            f.write(header)
            f.write(f"MOTION\nFrames: {total_frames}\nFrame Time: {1.0/fps:.6f}\n")

            for i in range(total_frames):
                v = []

                # Hips: Y=0（VRMモデルの自然な位置を使用）
                v.extend([0, 0, 0])  # position
                v.extend([0, 0, 0])  # rotation（回転なし）

                # Spine
                v.extend([angles['spine_z'][i], angles['spine_x'][i], 0])

                # Chest
                v.extend([angles['spine_z'][i] * 0.5, angles['spine_x'][i] * 0.5, 0])

                # UpperChest
                v.extend([0, 0, 0])

                # Neck
                v.extend([angles['head_z'][i] * 0.3, angles['head_x'][i] * 0.3, 0])

                # Head
                v.extend([angles['head_z'][i] * 0.5, angles['head_x'][i] * 0.5, 0])

                # L_Shoulder
                v.extend([0, 0, 0])

                # L_UpperArm
                v.extend([angles['l_arm_z'][i], angles['l_arm_x'][i], 0])

                # L_LowerArm
                v.extend([angles['l_elbow'][i], 0, 0])

                # L_Hand
                v.extend([0, 0, 0])

                # R_Shoulder
                v.extend([0, 0, 0])

                # R_UpperArm
                v.extend([angles['r_arm_z'][i], angles['r_arm_x'][i], 0])

                # R_LowerArm
                v.extend([angles['r_elbow'][i], 0, 0])

                # R_Hand
                v.extend([0, 0, 0])

                # L_UpperLeg
                v.extend([angles['l_leg_z'][i], angles['l_leg_x'][i], 0])

                # L_LowerLeg
                v.extend([0, angles['l_knee'][i], 0])

                # L_Foot
                v.extend([0, 0, 0])

                # R_UpperLeg
                v.extend([angles['r_leg_z'][i], angles['r_leg_x'][i], 0])

                # R_LowerLeg
                v.extend([0, angles['r_knee'][i], 0])

                # R_Foot
                v.extend([0, 0, 0])

                f.write(" ".join(f"{x:.4f}" for x in v) + "\n")


def main():
    video = sys.argv[1] if len(sys.argv) > 1 else "input/radio_exercise.mp4"
    output = sys.argv[2] if len(sys.argv) > 2 else "output/full_body_v3.bvh"
    start = float(sys.argv[3]) if len(sys.argv) > 3 else 10
    end = float(sys.argv[4]) if len(sys.argv) > 4 else None

    pipeline = FullBodyPipelineV3(sample_rate=2, smooth_sigma=2.0)
    pipeline.process_video(video, output, start_sec=start, end_sec=end)


if __name__ == "__main__":
    main()
