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
   9つのタスクが全て表示されることを確認：
   - jp.radio-calisthenics-together.orchestrator
   - jp.radio-calisthenics-together.caffeinate
   - jp.radio-calisthenics-together.prepare
   - jp.radio-calisthenics-together.monitor
   - jp.radio-calisthenics-together.start
   - jp.radio-calisthenics-together.bird
   - jp.radio-calisthenics-together.verify
   - jp.radio-calisthenics-together.stop
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
launchctl load ~/Library/LaunchAgents/jp.radio-calisthenics-together.orchestrator.plist
launchctl load ~/Library/LaunchAgents/jp.radio-calisthenics-together.caffeinate.plist
launchctl load ~/Library/LaunchAgents/jp.radio-calisthenics-together.prepare.plist
launchctl load ~/Library/LaunchAgents/jp.radio-calisthenics-together.monitor.plist
launchctl load ~/Library/LaunchAgents/jp.radio-calisthenics-together.start.plist
launchctl load ~/Library/LaunchAgents/jp.radio-calisthenics-together.bird.plist
launchctl load ~/Library/LaunchAgents/jp.radio-calisthenics-together.verify.plist
launchctl load ~/Library/LaunchAgents/jp.radio-calisthenics-together.stop.plist
launchctl load ~/Library/LaunchAgents/jp.radio-calisthenics-together.obs-restart.plist

# 確認
launchctl list | grep radio-calisthenics
```

### 自動修復機能

health_monitor.pyが未ロードのタスクを検出した場合、自動的にロードを試みる。
ただし、これは最後の砦であり、手動操作時に正しく全てをロードすることが前提。

## スケジュール

multi-trigger は launchd の wake 直後発火取りこぼし対策（2026-05-20 事故）。lock により実行は 1 回に収束する。

- 06:25/06:30/06:35 - orchestrator（prepare→start→stop を 1 プロセスで順序保証。caffeinate 50分を内部保持）
- 06:30/06:40/06:48 - caffeinate（Macスリープ抑止、22分間ロック保持）
- 06:30/06:40/06:50 - prepare（Docker/OBS起動 + OBS WebSocket health check）
- 06:45 - monitor（健全性チェック、YouTubeトークン検証含む）
- 06:59 - start（配信開始。host wrapper 経由、lock + Docker daemon 待機）
- 06:59 - bird（鳥オーバーレイ演出をランダム発火、約16分常駐）
- 07:01 - verify（配信中であることを YouTube API で検証、無ければ自動リトライ）
- 07:05 - stop（配信終了 + 翌日枠予約。host wrapper 経由、lock）
- 日曜 04:00 - obs-restart（OBS週次再起動、状態腐敗予防）

### plist テンプレートと実体の同期ルール

`config/launchd/` のテンプレートは**インストール済み実体と常に同期**させること。
2026-06-10 に start/stop テンプレートが事故対応前の「wrapper 無し直接 docker compose 実行」のまま放置されていたことが発覚（install_launchd.sh 再実行で 5/20-21 対策が巻き戻る地雷だった）。plist を変更したら必ずテンプレートにも反映する。

### スリープ対策

過去にMacスリープでstart.pyの`time.sleep`が中断され配信失敗した事例あり (2026-05-16)。対策:

1. **caffeinate plist** (06:48-07:10): launchdが起動できれば、その時点以降のスリープを抑止
2. **pmset repeat wake** (要sudo、別途設定): Macを06:45に確実にフルWakeさせる
   ```bash
   sudo pmset repeat wake MTWRFSU 06:45:00
   ```
   設定済か確認: `pmset -g sched`

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

## ループ規約 (agent loop)

実装タスクは「実装 → verifier 検証 → PASS まで修正」のループで進める。

1. **開始時**: `docs/agent-rules.md`（過去の失敗から蒸留したルール集）を必ず読む
2. **ルーブリック**: `docs/rubrics/feature.md` を `docs/rubrics/<タスク名>.md` にコピーし、
   タスク固有基準を記入してから実装に入る
3. **テスト失敗時**: 同じ修正を 2 度繰り返さない。再試行の前に必ず根本原因を診断する
4. **完了の自己判定禁止**: 完了したと思ったら verifier サブエージェントに該当ルーブリックの
   パスを渡して判定を依頼する。`VERDICT: PASS` が出るまで作業を継続し、完了報告しない
5. **FAIL 時**: `GAPS:` の各項目に対処してから、再度 verifier に判定を依頼する
6. **タスク失敗時**: 根本原因の調査後、汎用ルール 1 行に蒸留して `docs/agent-rules.md` に
   追記する（類似ルールとは統合）
