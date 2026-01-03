# Radio Calisthenics Together

毎朝のラジオ体操をYouTube Liveで自動配信するためのプロジェクトです。

## Phase 1 機能
- 指定時刻にOBSを自動起動し、配信を開始。
- 指定時間経過後に配信を自動停止。
- Macローカルの `launchd` による正確なスケジュール実行。

## クイックスタート (最短手順)

1. **リポジトリの準備**:
   ```bash
   git clone <repo_url>
   cd radio-calisthenics-together
   ```

2. **依存関係のインストール**:
   ```bash
   pip install -r requirements.txt
   ```

3. **設定の作成**:
   ```bash
   cp .env.example .env
   # .env を編集して OBS_WS_PASSWORD 等を設定してください
   ```

4. **動作確認 (手動)**:
   ```bash
   # OBSを起動して配信を開始できるか確認
   python3 scripts/start_stream.py

   # 現在の状態を確認
   python3 scripts/check_status.py

   # 配信を停止できるか確認
   python3 scripts/stop_stream.py
   ```

5. **自動スケジュールの登録**:
   ```bash
   ./scripts/install_launchd.sh
   ```

詳細なセットアップ手順や運用方法は [docs/01_phase1_setup.md](docs/01_phase1_setup.md) を参照してください。

## 今後の展望 (Phase 2+)
- 配信枠の自動作成（YouTube Data API）
- チャット連動（描画エンジンへの反映）
- クラウドサーバ（AWS/GCP）への移行検討
- モニタリング機能の強化

## ライセンス
[MIT LICENSE](LICENSE)
