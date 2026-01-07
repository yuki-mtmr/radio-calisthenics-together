import cv2
import mediapipe as mp
import numpy as np
import os
import subprocess
import shutil
from tqdm import tqdm

class VideoTracer:
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=2,
            enable_segmentation=True,
            min_detection_confidence=0.5, # 検出自体は少し緩めて見失いにくくする
            min_tracking_confidence=0.8, # 追跡の確からしさは厳しくしてブレを抑える
            smooth_landmarks=True
        )
        self.smooth_offset_x = 0.5
        self.smoothing_factor = 0.1
        self.last_pose_landmarks = None # 見失った時のための直前のポーズ
        self.output_dir = "output"
        os.makedirs(self.output_dir, exist_ok=True)
        # 背景画像の読み込み
        self.bg_path = "background.png"
        self.background = None
        if os.path.exists(self.bg_path):
            self.background = cv2.imread(self.bg_path)
            if self.background is not None:
                print("Background image loaded successfully.")
        else:
            print(f"Warning: Background image {self.bg_path} not found.")

    def process_video(self, input_path):
        cap = cv2.VideoCapture(input_path)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # 中間ファイルのパス
        temp_video = os.path.join(self.output_dir, "temp_skeleton.mp4")

        # 棒人間描画用のVideoWriter
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_video, fourcc, fps, (width, height))

        # 背景のリサイズ
        if self.background is not None:
            bg_image = cv2.resize(self.background, (width, height))
        else:
            bg_image = np.zeros((height, width, 3), dtype=np.uint8)

        print(f"Processing {total_frames} frames with centering and custom background...")

        for _ in tqdm(range(total_frames)):
            ret, frame = cap.read()
            if not ret:
                break

            # BGR to RGB
            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.pose.process(image_rgb)

            # 背景をコピー
            skeleton_frame = bg_image.copy()

            current_landmarks = results.pose_landmarks

            # もし今のフレームで見失っても、直前のポーズが残っていればそれを使う（ジャンプ対策）
            if not current_landmarks and self.last_pose_landmarks:
                current_landmarks = self.last_pose_landmarks
                # 少し透過させるなどして「推測」であることを出しても良いが、
                # ここでは安定性を優先してそのまま描画に回す

            if current_landmarks:
                # --- センタリングの計算 (腰を基準にして安定させる) ---
                # ランドマーク 23: left_hip, 24: right_hip
                # 腰の中央を水平方向の基準点にする
                hip_l = current_landmarks.landmark[23]
                hip_r = current_landmarks.landmark[24]

                # 腰が見えていれば腰で、見えていなければ全体の平均で計算
                if hip_l.visibility > 0.5 and hip_r.visibility > 0.5:
                    anchor_x = (hip_l.x + hip_r.x) / 2
                else:
                    x_coords = [lm.x for lm in current_landmarks.landmark]
                    anchor_x = sum(x_coords) / len(x_coords)

                # ターゲットのオフセット
                target_offset_x = 0.5 - anchor_x

                if _ == 0:
                    self.smooth_offset_x = target_offset_x
                else:
                    self.smooth_offset_x = (self.smooth_offset_x * (1 - self.smoothing_factor)) + (target_offset_x * self.smoothing_factor)

                # ランドマークを水平方向に移動させて描画
                for lm in current_landmarks.landmark:
                    lm.x += self.smooth_offset_x

                # 棒人間を描画（より太く、見やすく）
                self.mp_drawing.draw_landmarks(
                    skeleton_frame,
                    current_landmarks,
                    self.mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=self.mp_drawing.DrawingSpec(
                        color=(50, 255, 50), thickness=5, circle_radius=5
                    ),
                    connection_drawing_spec=self.mp_drawing.DrawingSpec(
                        color=(255, 255, 255), thickness=10
                    )
                )

                # 次のフレームのために記録
                self.last_pose_landmarks = current_landmarks

            out.write(skeleton_frame)

        cap.release()
        out.release()
        return temp_video

    def combine_with_audio(self, video_path, audio_path, final_output):
        print("Combining video with converted audio...")
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-strict", "experimental",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            final_output
        ]
        subprocess.run(cmd, check=True)

def main():
    tracer = VideoTracer()

    input_video = "/app/input/radio_calisthenics_video.mp4"
    converted_audio = "/app/input/radio-calisthenics_converted.wav"
    output_final = "/app/root_out/radio-calisthenics_stickman.mp4"

    if not os.path.exists(input_video):
        print(f"Error: Input video not found at {input_video}")
        return

    # 1. トレース動画の作成（背景あり、センタリング）
    temp_video = tracer.process_video(input_video)

    # 2. 音声合成
    if os.path.exists(converted_audio):
        tracer.combine_with_audio(temp_video, converted_audio, output_final)
        print(f"Finished! File saved to: {output_final}")
    else:
        print(f"Warning: Audio file not found. Outputting video only.")
        shutil.copy(temp_video, output_final)

if __name__ == "__main__":
    main()
