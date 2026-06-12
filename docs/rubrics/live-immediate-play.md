# ルーブリック: live-immediate-play（live 検知で即 PLAY + grace デッドライン）

> feature.md テンプレートからコピーし、タスク固有基準を記入済み（2026-06-12）。
> 背景: 06-12 朝、VOD 冒頭に約 30〜40 秒の静止フレーム（live 化 06:59:31 → PLAY 07:00:00 の定刻待ち）。
> ユーザー決定: live 化と同時に体操開始（開始時刻 ±15 秒のブレを許容）。頭切れゼロは維持。

## 検証コマンド（正）

```bash
.venv/bin/python -m pytest tests/ --ignore=tests/test_smpl_to_bvh.py -m "not slow" -p no:cacheprovider -q
```

- ベースライン: 272 passed（2026-06-11 video-selection 後）。本タスク完了時の期待値 **274 passed**

## 必須基準（全タスク共通）

1. **全テストがパス** — 上記コマンドで failed / error が 0
2. **根本原因の修正** — 対症療法でないこと（PLAY ポリシーの仕様変更として _wait_for_broadcast_live と main の該当箇所そのものを変更）
3. **デグレなし** — 無関係ファイルなし。仕様変更対象外のテスト（polls_until_live / survives_api_errors / hard_cap / setup / main 配線）は**無編集のまま緑**
4. **既存パターン準拠** — sleep_fn/now_fn 注入パターンを維持

## プロジェクト固有基準

### A. 契約テストの凍結

```bash
git diff --stat -- tests/test_stop_stream_contracts.py tests/test_prepare_environment_contracts.py
# → 出力なし + 両ファイル green
```

### B. エントリポイントは薄く

既存 scripts/start_stream.py 内ロジックの縮小のみ（新規ポーリングループ等の追加なし）→ 適合。

### C. ad-hoc sleep 禁止

```bash
git diff -U0 -- scripts/ src/ ':(exclude)src/rct/retry.py' | grep '^+' | grep 'time\.sleep'
# → 出力なし（time.sleep(remaining) の削除のみ。L80 の _sleep デフォルト行と L158 は無接触）
```

### D. plist テンプレート同期 — **N/A**（plist 無変更）

## タスク固有基準

- [ ] **live 検知後の即 PLAY**: live 検知と PLAY の間に待機なし
      — 検証: `test_main_plays_immediately_after_live_detection` green（STREAM_START_TIME=23:59 で決定的 RED→GREEN）
- [ ] **定刻超過でも live を待つ**（頭切れ防止の本体）: 定刻後・grace 内なら polling 継続
      — 検証: `test_wait_for_broadcast_live_keeps_polling_past_target_until_live` green
- [ ] **grace デッドラインで諦める**（verify 07:01 リトライ保護）: 定刻 +45 秒で False
      — 検証: `test_wait_for_broadcast_live_gives_up_at_grace_deadline` green ＋ 定数 `LIVE_GRACE_AFTER_TARGET_SEC == 45`
- [ ] **lead 短縮**: `PRE_START_LEAD_SEC == 15`、`LIVE_POLL_MAX_POLLS == 60` 維持
      — 検証: `test_lead_constants` green
- [ ] **RED 証憑**: テスト書き換え後・実装前に lead 定数 / past-target / plays-immediately の 3 件が fail
- [ ] **観測ログ**: live 検知時に定刻との差分が INFO ログに出る（翌朝の検証手段）。FAILURE_PATTERNS（Error:/Exception/Traceback）に該当する文字列を含まない

## 判定ルール

- 全基準 ✓ で PASS。1 つでも ✗ なら FAIL
- 「該当時のみ」基準は、非該当なら ✓（N/A）と明記する
