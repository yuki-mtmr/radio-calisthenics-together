#!/bin/bash
# RCT Video Processing (Stickman Pose Tracking) Launcher with Auto-Retry
set -e

cd "$(dirname "$0")/video_process"

echo "--- Video Processing via Docker (Auto-Retry Enabled) ---"

ROOT_DIR="$(cd .. && pwd)"
INPUT_VIDEO="$ROOT_DIR/ラジオ体操第一（通し）.mp4"
CONVERTED_AUDIO="$ROOT_DIR/radio-calisthenics_converted.wav"
OUTPUT_FILE="../radio-calisthenics_stickman.mp4"

# 1. ビルドの自動リトライループ
MAX_RETRIES=10
RETRY_COUNT=0

echo "Building Docker image..."
until docker build -t rct-video-proc .; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "Error: Docker build failed after $MAX_RETRIES attempts."
        exit 1
    fi
    echo "Build failed. Retrying in 10 seconds (Attempt $RETRY_COUNT/$MAX_RETRIES)..."
    sleep 10
done

echo "Build successful!"

# 2. 実行の自動リトライループ (通信エラー等で停止した場合)
# 映像処理は重いので、実行自体のリトライは慎重に行うが、
# ライブラリの動的ダウンロードやネットワーク系のエラーであればリトライが有効。
echo "Starting Video Trace inside Docker..."

RETRY_COUNT=0
until docker run --rm \
    -v "$INPUT_VIDEO:/app/input/radio_calisthenics_video.mp4" \
    -v "$CONVERTED_AUDIO:/app/input/radio-calisthenics_converted.wav" \
    -v "$ROOT_DIR:/app/root_out" \
    rct-video-proc; do

    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "Error: Docker run failed after $MAX_RETRIES attempts."
        exit 1
    fi
    echo "Run failed. Retrying in 10 seconds (Attempt $RETRY_COUNT/$MAX_RETRIES)..."
    sleep 10
done

echo "--- Process Finished Successfully! ---"
if [ -f "$OUTPUT_FILE" ]; then
    echo "Output created: radio-calisthenics_stickman.mp4"
else
    echo "Warning: Output file not found even though process reported success."
fi

read -p "Press any key to close..."
