# 運用手順 (Phase 1)

日々の運用の流れについて説明します。

## 1. 事前準備 (前日まで)
- YouTube Studioで翌朝の配信枠をスケジュール作成します。
- OBSに正しい配信キーが設定されていることを確認します。

## 2. 動作確認 (手動テスト)
インストール後または設定変更後は、手動でスクリプトを実行してテストしてください。

- **配信開始テスト**:
  ```bash
  python3 scripts/start_stream.py
  ```
- **ステータス確認**:
  ```bash
  python3 scripts/check_status.py
  ```
- **配信停止テスト**:
  ```bash
  python3 scripts/stop_stream.py
  ```

## 3. ログの確認
配信が成功したか、エラーが発生していないかは `logs/` ディレクトリ配下のファイルで確認できます。

- `logs/rct_YYYYMMDD.log`: アプリケーションの実行ログ
- `logs/start_stdout.log`, `logs/start_stderr.log`: launchd経由の出力
- `logs/stop_stdout.log`, `logs/stop_stderr.log`: launchd経由の出力

## 4. 失敗時の切り分け
1. **OBSが起動していない**: `scripts/start_stream.py` を実行して、エラーメッセージを確認してください。
2. **WebSocket接続エラー**: `.env` のパスワードとポートが、OBS側の設定と一致しているか確認してください。
3. **配信が始まらない**: OBSの「配信開始」ボタンを手動で押して、YouTubeに接続できるか確認してください（配信キーの期限切れなど）。
