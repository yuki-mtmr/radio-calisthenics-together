# ルーブリック: wedge-recovery-reachability (2026-07-17 配信失敗の恒久対策)

## 検証コマンド（正）

```bash
.venv/bin/python -m pytest tests/ -p no:cacheprovider -q
```

## 必須基準（全タスク共通）

1. **全テストがパス** — 上記コマンドで failed / error が 0
2. **根本原因の修正** — 対症療法でないこと。7/17 の失敗原因は「wedge 中は
   `docker info` が毎チェック 15s timeout を消費するため `wait_for_docker`
   (90 回) が最大 1530s に膨張し、prepare の deadline (1200s) が
   `_attempt_wedge_recovery` 到達より先に発火した」こと。修正がこの
   到達不能性そのものを解消しているか判定する
3. **デグレなし** — タスクと無関係のファイルが diff に含まれない。テストの削除・
   skip 追加・アサーション弱体化がない
4. **既存パターン準拠** — CLAUDE.md / 契約テスト凍結に適合

## プロジェクト固有基準

### A. 契約テストの凍結

```bash
git diff --stat -- tests/test_stop_stream_contracts.py tests/test_prepare_environment_contracts.py
# → 出力なし
```

### B. タスク固有基準

1. `docker_ops.wait_for_docker` が壁時計時間 (`max_total_seconds`) でも
   打ち切れること。未指定時は従来の回数制御と完全互換（既存タイミングテスト
   `test_wait_timeout_matches_legacy_timing` が未編集のまま green）
2. `prepare_environment.wait_for_docker` と wedge 復旧後の `_wait_ready` の
   両方が `max_total_seconds=180` を渡すこと（テストで契約化されている）
3. 最悪ケースの数値検算: wedge 時の全経路
   (初回判定 + 3 リトライ + wedge 判定 + 復旧待機) の合計が
   prepare の DEADLINE_SECONDS (1200s) を下回ることをコード上の定数から
   説明できること
4. 注入可能性の維持: 新パラメータ (`monotonic`) がテストから注入可能で、
   実時間に依存するテストがないこと
