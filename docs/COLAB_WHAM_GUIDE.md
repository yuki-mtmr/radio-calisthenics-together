# Google ColabでWHAMを実行する手順

## 概要
Google Colabを使用してWHAMモーションキャプチャを実行し、結果をダウンロードします。

## 前提条件
- Googleアカウント
- SMPLの登録（https://smpl.is.tue.mpg.de/）

## 手順

### Step 1: 動画をGoogle Driveにアップロード
1. Google Drive（https://drive.google.com/）を開く
2. `radio_right_person.mp4`（デスクトップにコピー済み）をアップロード
3. アップロード先のパスをメモ（例: `/content/drive/MyDrive/radio_right_person.mp4`）

### Step 2: WHAMのColabノートブックを開く
以下のリンクからノートブックを開く：
https://colab.research.google.com/drive/1ysUtGSwidTQIdBQRhq0hj63KbseFujkn?usp=sharing

### Step 3: セットアップセルを実行
1. 「ランタイム」→「すべてのセルを実行」を選択するか、各セルを順番に実行
2. SMPLの認証情報（ユーザー名・パスワード）を入力

### Step 4: 動画パスを変更
デモビデオのパスを自分の動画に変更：

```python
# 変更前
video_path = "examples/IMG_9732.mov"

# 変更後（Google Driveをマウント後）
from google.colab import drive
drive.mount('/content/drive')

video_path = "/content/drive/MyDrive/radio_right_person.mp4"
```

### Step 5: 実行
```python
# カメラ座標系のみで実行（SLAMなし - 高速）
!python demo.py --video {video_path} --visualize --estimate_local_only
```

### Step 6: 結果をダウンロード
結果は `output/` ディレクトリに保存されます：

```python
# 結果をzipにまとめてダウンロード
import shutil
shutil.make_archive('/content/wham_output', 'zip', '/content/WHAM/output')

from google.colab import files
files.download('/content/wham_output.zip')
```

## 出力ファイル
- `wham_output.pkl` - SMPLパラメータ（poses, betas, trans）
- `render_*.mp4` - 可視化動画（オプション）

## ローカルでの後処理
ダウンロードしたファイルを `output/wham_result/` に配置してBVH変換を実行：

```bash
cd /Users/yukimatsumori/projects/radio-calisthenics-together
python scripts/smpl_to_bvh_converter.py \
    --input output/wham_result/wham_output.pkl \
    --output output/radio_wham.bvh
```

## トラブルシューティング

### メモリ不足
動画が長い場合はメモリ不足になる可能性があります。対策：
1. 動画を分割して処理
2. 解像度を下げる
3. Colab Pro を使用

### 処理時間
- 3分の動画: 約10-20分（GPU使用時）
- `--estimate_local_only`フラグで高速化可能
