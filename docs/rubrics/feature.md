# ルーブリック: <タスク名>

> 運用: このファイルはテンプレート。タスク開始時に `docs/rubrics/<タスク名>.md` へコピーし、
> 「タスク固有基準」を記入してから実装を始める。テンプレート自体は編集しない。

## 検証コマンド（正）

```bash
.venv/bin/python -m pytest tests/ -p no:cacheprovider -q
```

- 実測: 277 passed / 約 4 分半（2026-06-12 分離後）。verifier はループ 1 周ごとにこれを実行する
- 2026-06-12: コンテンツ生成系（WHAM / BVH / Blender / mediapipe / 生成 CLI）は
  `../radio-calisthenics-studio` へ分離した。numpy・Blender 依存テストも同リポジトリへ
  移動したため、旧来の `--ignore=tests/test_smpl_to_bvh.py` と `-m "not slow"` は不要になった
- 生成パイプラインを触るタスクは studio リポジトリ側のルーブリックで検証する
  （このリポジトリの検証対象は配信プレイヤーのみ。studio から `videos/` へ入る mp4 の
  受け入れ要件は `studio publish` 側が検証する）
- Docker 代替: `docker compose run --rm rct python -m pytest tests/`
  （分離により numpy / Blender / WHAM 依存テストが退去し、2026-06-12 に 277 passed で green 確認済み）

## 必須基準（全タスク共通）

1. **全テストがパス** — 上記コマンドで failed / error が 0
2. **根本原因の修正** — 対症療法（テスト期待値の書き換え、例外の握り潰し、sleep 追加）で
   ないこと。git diff を読み、失敗原因の発生箇所そのものを変更しているか判定する
3. **デグレなし** — タスクと無関係のファイルが diff に含まれない。テストの削除・skip 追加・
   アサーション弱体化がない（`git diff -- tests/` で確認）
4. **既存パターン準拠** — 下記プロジェクト固有基準および CLAUDE.md に適合

## プロジェクト固有基準

### A. 契約テストの凍結

事故対応で調整済みの定数・文字列（retry 間隔、配信タイトル形式等）は契約。
契約テストが**未編集のまま** green であること:

```bash
git diff --stat -- tests/test_stop_stream_contracts.py tests/test_prepare_environment_contracts.py
# → 出力なし
.venv/bin/python -m pytest tests/test_stop_stream_contracts.py tests/test_prepare_environment_contracts.py -p no:cacheprovider -q
# → green
```

### B. エントリポイントは薄く

新しいドメインロジックは `src/rct/` 配下に置き、`scripts/` は配線のみ。

```bash
git diff -- scripts/
# → リトライループ・ポーリング・API 呼び出しロジックの新規実装が無いことを読んで判定
```

### C. ad-hoc sleep 禁止（2026-05-16 スリープ事故由来）

待機・リトライは `rct.retry`（`RetryPolicy` / `run_with_retry` / `poll_until`）、
多重起動防止は `rct.lockfile` を再利用する。

```bash
git diff -U0 -- scripts/ src/ ':(exclude)src/rct/retry.py' | grep '^+' | grep 'time\.sleep'
# → 出力なし
```

### D. （該当時のみ）plist テンプレート同期（2026-06-10 事故由来）

launchd plist を変更した場合、`config/launchd/` テンプレート（プレースホルダ展開後）と
インストール済み実体が一致すること。リポジトリルートで実行:

```bash
for f in config/launchd/*.plist; do
  diff <(sed -e "s|{{REPO_DIR}}|$PWD|g" -e "s|{{USER}}|$USER|g" "$f") \
       ~/Library/LaunchAgents/"$(basename "$f")"
done
# → 差分なし（plist を触っていないタスクは N/A）
```

## タスク固有基準（コピー後に記入）

- [ ] <受け入れ条件 1> — 検証: <コマンド or 確認手順>
- [ ] <受け入れ条件 2> — 検証: <コマンド or 確認手順>

## 判定ルール

- 全基準 ✓ で PASS。1 つでも ✗ なら FAIL
- 「該当時のみ」基準は、非該当なら ✓（N/A）と明記する
