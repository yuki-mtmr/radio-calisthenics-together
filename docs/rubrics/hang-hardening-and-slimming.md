# ルーブリック: hang-hardening-and-slimming

> 元テンプレート: feature.md（2026-07-10 コピー）
> 背景: 2026-07-07 06:25 に Docker Desktop backend が wedge（socket 接続可・応答なし）し、
> timeout なしの `docker info` で orchestrator / prepare / health_monitor / start / stop / bird の
> 全プロセスが 3 日間ハング。lock を握り続けたため以降の全 trigger と verify のリカバリが
> 「already running, skipping」で弾かれ、7/7〜7/10 の配信が 4 日連続停止。アラートも
> 「失敗」ではなく「永久待機」のため一切飛ばなかった。

## 検証コマンド（正）

```bash
.venv/bin/python -m pytest tests/ -p no:cacheprovider -q
```

- 実測: 277 passed / 約 4 分半（2026-06-12 分離後）。verifier はループ 1 周ごとにこれを実行する
- Docker 代替: `docker compose run --rm rct python -m pytest tests/`

## 必須基準（全タスク共通）

1. **全テストがパス** — 上記コマンドで failed / error が 0
2. **根本原因の修正** — 対症療法（テスト期待値の書き換え、例外の握り潰し、sleep 追加）でないこと
3. **デグレなし** — タスクと無関係のファイルが diff に含まれない。テストの削除・skip 追加・アサーション弱体化がない
4. **既存パターン準拠** — プロジェクト固有基準および CLAUDE.md に適合

## プロジェクト固有基準

### A. 契約テストの凍結

```bash
git diff --stat -- tests/test_stop_stream_contracts.py tests/test_prepare_environment_contracts.py
# → 出力なし
.venv/bin/python -m pytest tests/test_stop_stream_contracts.py tests/test_prepare_environment_contracts.py -p no:cacheprovider -q
# → green
```

### B. エントリポイントは薄く — 新ロジックは `src/rct/`、`scripts/` は配線のみ

### C. ad-hoc sleep 禁止 — 待機・リトライは `rct.retry`、多重起動防止は `rct.lockfile`

```bash
git diff -U0 -- scripts/ src/ ':(exclude)src/rct/retry.py' | grep '^+' | grep 'time\.sleep'
# → 出力なし
```

### D. plist テンプレート同期（plist を変更した場合のみ）

```bash
for f in config/launchd/*.plist; do
  diff <(sed -e "s|{{REPO_DIR}}|$PWD|g" -e "s|{{USER}}|$USER|g" "$f") \
       ~/Library/LaunchAgents/"$(basename "$f")"
done
# → 差分なし
```

## タスク固有基準

### T1: ハング根絶（timeout）

- [ ] `rct.docker_ops.is_docker_ready` に subprocess timeout（既定 15s 程度）があり、
      `TimeoutExpired` を「not ready」として扱う — 検証: `tests/test_docker_ops.py` に
      TimeoutExpired ケースのテストが追加され green
- [ ] リポジトリ内に「timeout なしで外部コマンドを無限待ちし得る subprocess 呼び出し」が
      配信経路（prepare / start / stop / orchestrator / health_monitor / verify / bird）に残っていない
      — 検証: grep + コードレビューで確認（`open`/`pgrep` 等の即時終了コマンドは対象外）

### T2: Docker wedge 自動復旧

- [ ] prepare 実行時、`docker info` が連続 timeout（= wedge。プロセス生存 + 応答なし）の場合に
      Docker Desktop を強制再起動（pkill → open -a Docker → ready 待ち）し、アラートメールを送る
      — 検証: ユニットテスト（subprocess をモック）で wedge→restart 経路を確認

### T3: プロセス滞留 watchdog + 実行時間上限

- [ ] orchestrator / prepare / start / stop / monitor の各エントリポイントに全体 deadline
      （SIGALRM 等）があり、超過時に「アラートメール送信 + 非ゼロ終了」する
      — 検証: deadline モジュールのユニットテストが green
- [ ] health_monitor が「配信系スクリプトの規定時間超過プロセス」を検出したら kill + アラートする
      — 検証: ユニットテスト（ps 出力モック）で検出→kill 経路を確認
- [ ] health_monitor 自身のチェック（docker info / YouTube API）にも timeout があり、
      last line of defense がハングしない — 検証: テストで確認

### T4: youtube-autopost への移行

- [ ] `src/rct/youtube_client.py` を削除し、全参照が `youtube_autopost` ライブラリ経由になる
      — 検証: `grep -rn "rct.youtube_client\|rct\.youtube_client" scripts/ src/ tests/` → 出力なし
- [ ] Docker イメージ・host `.venv` の両方で `youtube_autopost` が import 可能
      — 検証: `docker compose run --rm rct python -c "import youtube_autopost"` と
      `.venv/bin/python -c "import youtube_autopost"` が成功
- [ ] 日次フロー（06:59 の compose run）がネットワーク非依存でビルド済みイメージのみで動く
      （vendored wheel or 同等の方式）
- [ ] 既存の挙動契約（配信タイトル形式・リトライ回数・アラート文言）が変わらない
      — 検証: 契約テスト green + youtube 系テストが移行後も同等のカバレッジで green

### T5: リポジトリスリム化

- [ ] 生成系の残骸（ルート直下の .wav / .mp4、その他 inventory で dead 判定されたもの）が
      削除されている — 検証: `ls` + git status
- [ ] README.md / CLAUDE.md に 3 リポジトリの役割分担（player / studio / youtube-autopost）が
      明記されている
- [ ] `docs/agent-rules.md` に今回の教訓が汎用ルール 1 行で追記されている

## 判定ルール

- 全基準 ✓ で PASS。1 つでも ✗ なら FAIL
- 「該当時のみ」基準は、非該当なら ✓（N/A）と明記する
