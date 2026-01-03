# トラブルシューティング

## OBSが起動しない
- `.env` の `OBS_PATH` が正しいか確認してください（デフォルトは `/Applications/OBS.app/Contents/MacOS/OBS`）。
- ターミナルから直接そのパスを実行して、OBSが立ち上がるか試してください。

## WebSocketに接続できない
- OBSの `設定` > `WebSocketサーバーの設定` で `WebSocketサーバーを有効にする` がチェックされているか。
- パスワードが正しいか。
- `127.0.0.1` 以外（ホスト名など）を使っている場合、ファイアウォールでブロックされていないか。

## 配信が開始されない
- OBSの「配信」設定が正しいか。
- シーン名 (`OBS_SCENE_NAME`) がOBS上に実在するか。
- YouTube側で配信枠がアクティブになっているか。

## Macがスリープして止まる
- Macの電源設定を確認してください。
- `caffeinate` コマンドを plist に含める等の対策を検討してください。

## launchdが動かない
- `scripts/install_launchd.sh` を再実行して、plistが `~/Library/LaunchAgents` に正しくコピーされたか確認してください。
- `logs/start_stderr.log` を見て、Pythonの実行エラー（モジュール不足など）がないか確認してください。
- Pythonのフルパスを確認してください。macOS標準は `/usr/bin/python3` ですが、Homebrew等を使っている場合はパスが異なる場合があります。
  - `which python3` で確認したパスを `jp.radio-calisthenics-together.start.plist` 内の `<string>/usr/bin/python3</string>` と書き換える必要があります。
