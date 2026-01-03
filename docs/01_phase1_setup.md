# セットアップガイド (Phase 1)

Phase 1を動作させるための準備手順です。

## 1. OBSの準備
1. **OBS Studio** をインストールします。
2. **配信設定**:
   - `設定` > `配信` を開きます。
   - **重要**: 現在のOBSではYouTubeアカウントを直接連携する方式がデフォルトです。
   - **方法A: アカウント連携 (推奨)**:
     - 「アカウント連携」ボタンでログインします。
     - 配信時は、メイン画面の「配信の管理」ボタンからスケジュールした枠を選択します。
   - **方法B: 配信キーを使用する (自動化向き)**:
     - アカウントが連携されている場合は一度「アカウントを切断」します。
     - 「配信キーを使用する (高度)」ボタンをクリックすると、配信キーの入力欄が表示されます。
     - YouTube Studioから取得した配信キーを貼り付けます。
3. **obs-websocket** を有効化します。
   - **Macメニューバー** > `ツール` > `WebSocket サーバーの設定` を開きます。
   - `WebSocketサーバーを有効にする` にチェック。
   - `サーバーポート` (4455) と `サーバーパスワード` を設定します。
4. **シーンの作成**:
   - 配信したい内容を含むシーンを作成します。名前を `.env` の `OBS_SCENE_NAME` と一致させます（例: `RADIO_TAISO_LOOP`）。

## 2. YouTubeの準備
1. YouTube Studio にて「ライブ配信」画面を開きます。
2. 「スケジュール設定」で翌朝の枠を作成します。
3. **配信キーの取得**:
   - スケジュールした配信の管理画面に「ストリームキー」が表示されます。
   - これをコピーして、OBS側の「配信キー」欄（方法Bの場合）に設定します。

## 3. 実行環境の準備 (Docker)
1. **Docker Desktop** がインストール・起動されていることを確認します。
2. **イメージのビルド**:
   ```bash
   docker compose build
   ```
3. **.env の設定**:
   - `OBS_WS_HOST` は `host.docker.internal` に設定してください（Dockerコンテナから見てホストのMacを指します）。
   ```bash
   OBS_WS_HOST=host.docker.internal
   OBS_WS_PORT=4455
   OBS_WS_PASSWORD=あなたのパスワード
   ```

## 4. 動作確認 (Docker)
Docker経由でスクリプトを実行します。

- **状態確認**:
  ```bash
  docker compose run --rm rct python scripts/check_status.py
  ```
- **配信開始**:
  ```bash
  docker compose run --rm rct python scripts/start_stream.py
  ```

## 5. Macのスリープ無効化
配信時間にMacがスリープしているとDockerも止まるため、必ずスリープを無効にしてください。
- `システム設定` > `ディスプレイ` > `詳細設定...` > `電源アダプタ使用時はディスプレイがオフのときに自動でスリープさせない` をオンにする。

## 6. launchd の導入 (Docker版)
Dockerコマンドをスケジュール実行するように plist を構成します。
※ `scripts/install_launchd.sh` を実行すると、Docker経由で実行する設定が登録されます。
