#!/bin/bash
#
# VRMアバター ラジオ体操アニメーション パイプライン
#
# 使用方法:
#   ./scripts/run_vrm_animation_pipeline.sh [options]
#
# オプション:
#   --skip-wham    WHAMステップをスキップ（既にSMPLデータがある場合）
#   --help         ヘルプを表示
#

set -e

# プロジェクトルート
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# 定数
VRM_FILE="assets/character.vrm"
INPUT_VIDEO="output/radio_right_person.mp4"
WHAM_OUTPUT_DIR="output/wham_result"
BVH_OUTPUT="output/radio_wham.bvh"
FINAL_OUTPUT="output/radio_vrm_final.mp4"
BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"

# 色付き出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    echo "VRMアバター ラジオ体操アニメーション パイプライン"
    echo ""
    echo "使用方法:"
    echo "  ./scripts/run_vrm_animation_pipeline.sh [options]"
    echo ""
    echo "オプション:"
    echo "  --skip-wham    WHAMステップをスキップ（既にSMPLデータがある場合）"
    echo "  --help         このヘルプを表示"
    echo ""
    echo "ワークフロー:"
    echo "  1. [手動] Google ColabでWHAMを実行 → SMPLパラメータ取得"
    echo "  2. [自動] SMPL → BVH変換"
    echo "  3. [自動] BVH → VRM適用 & レンダリング"
    echo ""
    echo "前提条件:"
    echo "  - Blenderがインストールされていること"
    echo "  - VRMアドオンがインストールされていること（推奨）"
    echo "  - 入力ファイル: $INPUT_VIDEO"
    echo "  - VRMモデル: $VRM_FILE"
}

check_prerequisites() {
    log_info "前提条件を確認中..."

    # Blenderの確認
    if [ ! -f "$BLENDER" ]; then
        log_error "Blenderが見つかりません: $BLENDER"
        exit 1
    fi

    # VRMファイルの確認
    if [ ! -f "$VRM_FILE" ]; then
        log_error "VRMファイルが見つかりません: $VRM_FILE"
        exit 1
    fi

    # 入力動画の確認
    if [ ! -f "$INPUT_VIDEO" ]; then
        log_error "入力動画が見つかりません: $INPUT_VIDEO"
        exit 1
    fi

    log_info "前提条件OK"
}

step1_wham_instructions() {
    log_info "=== Step 1: WHAMでモーションキャプチャ ==="
    echo ""
    echo "Google ColabでWHAMを実行してください："
    echo ""
    echo "1. 動画をGoogle Driveにアップロード:"
    echo "   ファイル: $INPUT_VIDEO"
    echo ""
    echo "2. Colabノートブックを開く:"
    echo "   https://colab.research.google.com/drive/1ysUtGSwidTQIdBQRhq0hj63KbseFujkn"
    echo ""
    echo "3. 詳細な手順は docs/COLAB_WHAM_GUIDE.md を参照"
    echo ""
    echo "4. 結果をダウンロードして以下に配置:"
    echo "   $WHAM_OUTPUT_DIR/"
    echo ""
    read -p "WHAMの結果を配置したらEnterキーを押してください..."

    # 出力ディレクトリの確認
    if [ ! -d "$WHAM_OUTPUT_DIR" ]; then
        log_warn "WHAMの出力ディレクトリが見つかりません: $WHAM_OUTPUT_DIR"
        log_warn "ディレクトリを作成してファイルを配置してください"
        mkdir -p "$WHAM_OUTPUT_DIR"
        exit 1
    fi
}

step2_smpl_to_bvh() {
    log_info "=== Step 2: SMPL → BVH変換 ==="

    # WHAMの出力ファイルを探す
    SMPL_FILE=""
    for ext in pkl npz; do
        for f in "$WHAM_OUTPUT_DIR"/*.$ext; do
            if [ -f "$f" ]; then
                SMPL_FILE="$f"
                break 2
            fi
        done
    done

    if [ -z "$SMPL_FILE" ]; then
        log_error "SMPLパラメータファイルが見つかりません: $WHAM_OUTPUT_DIR/*.pkl or *.npz"
        exit 1
    fi

    log_info "入力: $SMPL_FILE"
    log_info "出力: $BVH_OUTPUT"

    # 仮想環境を有効化
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    elif [ -d ".venv_wham" ]; then
        source .venv_wham/bin/activate
    fi

    # 変換実行
    python scripts/smpl_to_bvh_converter.py \
        --input "$SMPL_FILE" \
        --output "$BVH_OUTPUT" \
        --fps 30

    if [ ! -f "$BVH_OUTPUT" ]; then
        log_error "BVH変換に失敗しました"
        exit 1
    fi

    log_info "BVH変換完了: $BVH_OUTPUT"
}

step3_apply_to_vrm() {
    log_info "=== Step 3: BVH → VRM適用 & レンダリング ==="

    if [ ! -f "$BVH_OUTPUT" ]; then
        log_error "BVHファイルが見つかりません: $BVH_OUTPUT"
        exit 1
    fi

    log_info "VRM: $VRM_FILE"
    log_info "BVH: $BVH_OUTPUT"
    log_info "出力: $FINAL_OUTPUT"

    # Blenderでスクリプトを実行
    "$BLENDER" --background --python scripts/apply_bvh_to_vrm.py -- \
        --vrm "$VRM_FILE" \
        --bvh "$BVH_OUTPUT" \
        --output "$FINAL_OUTPUT" \
        --width 1280 \
        --height 720 \
        --fps 30

    if [ ! -f "$FINAL_OUTPUT" ]; then
        log_error "レンダリングに失敗しました"
        exit 1
    fi

    log_info "レンダリング完了: $FINAL_OUTPUT"
}

# メイン処理
main() {
    SKIP_WHAM=false

    # 引数解析
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-wham)
                SKIP_WHAM=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_error "不明なオプション: $1"
                show_help
                exit 1
                ;;
        esac
    done

    echo "================================================"
    echo " VRMアバター ラジオ体操アニメーション パイプライン"
    echo "================================================"
    echo ""

    # 前提条件チェック
    check_prerequisites

    # Step 1: WHAM（手動）
    if [ "$SKIP_WHAM" = false ]; then
        step1_wham_instructions
    else
        log_info "WHAMステップをスキップ"
    fi

    # Step 2: SMPL → BVH
    step2_smpl_to_bvh

    # Step 3: BVH → VRM
    step3_apply_to_vrm

    echo ""
    log_info "================================================"
    log_info " パイプライン完了！"
    log_info "================================================"
    log_info "出力ファイル: $FINAL_OUTPUT"
    echo ""
    echo "確認方法:"
    echo "  open $FINAL_OUTPUT"
}

main "$@"
