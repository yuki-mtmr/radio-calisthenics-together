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
            min_detection_confidence=0.5
        )
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

            if results.pose_landmarks:
                # センタリングの計算
                # すべてのランドマークのX座標の平均を求める
                x_coords = [lm.x for lm in results.pose_landmarks.landmark]
                avg_x = sum(x_coords) / len(x_coords)

                # 0.5 がフレームの水平方向の中央
                # （元が右寄りなら avg_x > 0.5 なので、offset_x はマイナスになる）
                offset_x = 0.5 - avg_x

                # ランドマークを水平方向に移動させる
                for lm in results.pose_landmarks.landmark:
                    lm.x += offset_x

                # 棒人間（骨格）のみを描画
                self.mp_drawing.draw_landmarks(
                    skeleton_frame,
                    results.pose_landmarks,
                    self.mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=self.mp_drawing.DrawingSpec(color=(50, 255, 50), thickness=4, circle_radius=4),
                    connection_drawing_spec=self.mp_drawing.DrawingSpec(color=(255, 255, 255), thickness=8)
                )

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
