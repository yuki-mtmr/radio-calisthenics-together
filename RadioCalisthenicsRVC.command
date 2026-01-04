#!/bin/bash
# RCT Audio Processing (RVC) Launcher
set -e

cd "$(dirname "$0")/audio_process"

echo "--- Audio Processing via Docker ---"

# Dockerイメージのビルド
echo "Building Docker image for audio processing..."
docker build -t rct-audio-proc .

# 実行 (ホストの入出力をマウント)
echo "Starting Audio Process inside Docker..."
ROOT_DIR="$(cd .. && pwd)"

docker run --rm \
    -v "$ROOT_DIR/radio-calisthenics.wav:/app/input/radio-calisthenics.wav" \
    -v "$(pwd)/models:/app/models" \
    -v "$(pwd)/output:/app/output" \
    -v "$ROOT_DIR:/app/root_out" \
    rct-audio-proc python main.py

# 結果のコピーは main.py 内で行われるが、念のためルートを確認
if [ -f "$ROOT_DIR/radio-calisthenics_converted.wav" ]; then
    echo "--- Process Finished Successfully! ---"
    echo "Output: radio-calisthenics_converted.wav"
else
    echo "Warning: Final output file not found in root."
fi

echo "--- All Done ---"
read -p "Press any key to close..."
