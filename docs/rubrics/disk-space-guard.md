# ルーブリック: disk-space-guard

> 由来: 2026-08-06 インシデント。ホストのディスク満杯 (`[Errno 28] No space left on device`)
> により YouTube トークン更新・verify・stop が全滅し、配信が一度も live にならず、
> 翌日枠の予約も実行されなかった。health_monitor は 06:45 に検知したが
> **アラートを出すだけでフローを止めず**、start は空き容量を一切見ていなかった。

## 検証コマンド（正）

```bash
.venv/bin/python -m pytest tests/ -p no:cacheprovider -q
```

## 必須基準（全タスク共通）

1. **全テストがパス** — failed / error が 0
2. **根本原因の修正** — 対症療法でないこと
3. **デグレなし** — 無関係ファイルが diff に無い。テスト削除・skip・アサーション弱体化なし
4. **既存パターン準拠** — 下記プロジェクト固有基準および CLAUDE.md に適合

## プロジェクト固有基準

### A. 契約テストの凍結

```bash
git diff --stat -- tests/test_stop_stream_contracts.py tests/test_prepare_environment_contracts.py
# → 出力なし
```

### B. エントリポイントは薄く

新しいドメインロジックは `src/rct/` 配下（`src/rct/disk.py`）に置き、`scripts/` は配線のみ。

### C. ad-hoc sleep 禁止

```bash
git diff -U0 -- scripts/ src/ ':(exclude)src/rct/retry.py' | grep '^+' | grep 'time\.sleep'
# → 出力なし
```

### D. plist テンプレート同期 — 本タスクでは plist を変更しないため N/A

## タスク固有基準

- [ ] 1. `src/rct/disk.py` が空き容量を判定し、`ok` / `warn` / `critical` の 3 段階を返す
      — 検証: `pytest tests/test_disk.py`
- [ ] 2. 判定は注入可能（`usage_fn`）で、実 FS に依存せずテストできる
      — 検証: `tests/test_disk.py` が `shutil.disk_usage` を触らずに全分岐を通す
- [ ] 3. 閾値は `.env` / settings 経由で変更可能（既定 critical=5GB / warn=20GB）
      — 検証: `pytest tests/test_settings.py`
- [ ] 4. **health_monitor が critical 時に issue を上げる**（既存の他チェックと同じ経路で通知）
      — 検証: `pytest tests/test_health_monitor.py`
- [ ] 5. **health_monitor は結果に関わらず空き容量を毎回 INFO ログに残す**（推移追跡のため）
      — 検証: `pytest tests/test_health_monitor.py`
- [ ] 6. **prepare_environment が critical 時に Docker 起動より前に中断する**
      （アラート送信 + `sys.exit(1)`）。今回の穴＝検知しても止めなかったことの直接の修正
      — 検証: `pytest tests/test_prepare_environment.py`
- [ ] 7. warn 段階では中断せず、警告ログのみで続行する（誤爆で配信を落とさない）
      — 検証: `pytest tests/test_prepare_environment.py`

## 判定ルール

- 全基準 ✓ で PASS。1 つでも ✗ なら FAIL

### 追記 2026-08-28（orchestrator 貫通）

- [ ] 8. **orchestrator は prepare の非ゼロ終了で start/stop を実行しない**
      （8/27–28: prepare が critical で exit 1 しても戻り値を捨てて start に進んでいた。
      前日から Docker が生きていたので偶然成功していただけ）
      — 検証: `pytest tests/test_orchestrator.py -k prepare_fails`
- [ ] 9. テストが実 FS 状態に依存しない（`check_free_space` を no-notification 系テストで必ずモック。
      実機がディスク不足の時に無関係テストが落ちた 8/28 の再発防止）
      — 検証: 上記 `tests/test_health_monitor.py` / `tests/test_prepare_environment.py` で `_DISK_OK` 注入
