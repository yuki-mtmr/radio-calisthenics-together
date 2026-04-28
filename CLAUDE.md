# Radio Calisthenics Together - プロジェクト固有ルール

## launchd操作ルール

### 必須確認事項

launchdのplistを操作する際は、以下を必ず守ること：

1. **unload後は必ず全plistをロード**
   - `launchctl unload`でワイルドカードを使った場合、アンロードされた全てのplistを個別に`load`すること
   - 一部だけロードして他を忘れることは絶対に禁止

2. **操作後の確認コマンド**
   ```bash
   launchctl list | grep radio-calisthenics
   ```
   6つのタスクが全て表示されることを確認：
   - jp.radio-calisthenics-together.prepare
   - jp.radio-calisthenics-together.start
   - jp.radio-calisthenics-together.stop
   - jp.radio-calisthenics-together.monitor
   - jp.radio-calisthenics-together.bird
   - jp.radio-calisthenics-together.obs-restart

3. **plistファイルの場所**
   ```
   ~/Library/LaunchAgents/jp.radio-calisthenics-together.*.plist
   ```

### 正しい再読み込み手順

```bash
# 全てアンロード
launchctl unload ~/Library/LaunchAgents/jp.radio-calisthenics-together.*.plist

# 全てロード（個別に指定）
launchctl load ~/Library/LaunchAgents/jp.radio-calisthenics-together.prepare.plist
launchctl load ~/Library/LaunchAgents/jp.radio-calisthenics-together.start.plist
launchctl load ~/Library/LaunchAgents/jp.radio-calisthenics-together.stop.plist
launchctl load ~/Library/LaunchAgents/jp.radio-calisthenics-together.monitor.plist
launchctl load ~/Library/LaunchAgents/jp.radio-calisthenics-together.bird.plist
launchctl load ~/Library/LaunchAgents/jp.radio-calisthenics-together.obs-restart.plist

# 確認
launchctl list | grep radio-calisthenics
```

### 自動修復機能

health_monitor.pyが未ロードのタスクを検出した場合、自動的にロードを試みる。
ただし、これは最後の砦であり、手動操作時に正しく全てをロードすることが前提。

## スケジュール

- 06:45 - monitor（健全性チェック、YouTubeトークン検証含む）
- 06:50 - prepare（Docker/OBS起動）
- 06:59 - start（配信開始）
- 06:59 - bird（鳥オーバーレイ演出をランダム発火、約16分常駐）
- 07:15 - stop（配信終了）
- 日曜 04:00 - obs-restart（OBS週次再起動、状態腐敗予防）

## 鳥オーバーレイ演出 (bird overlay)

配信中、ランダムな確率で鳥が画面を横切る。

### OBS 側の事前セットアップ（手動・1回だけ）

1. シーン `RADIO_TAISO_LOOP` に Browser Source を追加
2. 名前: `bird_overlay`（`.env` の `OBS_BIRD_SOURCE_NAME` と一致させる）
3. `Local file` をチェックし、`assets/overlays/bird/index.html` を指定
4. Width: 1920, Height: 1080
5. デフォルトで非表示（目のアイコンOFF）にしておく
6. 「ソースが非アクティブの時にシャットダウン」をON、「表示時にブラウザを更新」をON

### 動作パラメータ（.env で調整）

- `BIRD_PROBABILITY=0.15` — 30秒ごとの発火確率
- `BIRD_INTERVAL_SEC=30` — 判定間隔
- `BIRD_SHOW_DURATION_SEC=7` — 鳥の表示時間
- `BIRD_DURATION_SEC=960` — director の常駐時間（デフォ16分）

### 手動テスト

```bash
docker compose run --rm rct python scripts/bird_director.py \
  --duration 30 --interval 5 --probability 0.5
```
