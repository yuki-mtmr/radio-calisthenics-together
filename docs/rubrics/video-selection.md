# ルーブリック: video-selection（配信動画選択機能 + 管理画面整備 + デスクトップショートカット）

> feature.md テンプレートからコピーし、タスク固有基準を記入済み（2026-06-11）。

## 検証コマンド（正）

```bash
.venv/bin/python -m pytest tests/ --ignore=tests/test_smpl_to_bvh.py -m "not slow" -p no:cacheprovider -q
```

- 実測: 254 passed / 約 4 分半（2026-06-11）。verifier はループ 1 周ごとにこれを実行する
- `test_smpl_to_bvh.py` はメイン venv に無い numpy をモジュールレベル import するため除外
  （モーション生成ドメイン）。`-m "not slow"` は Blender をサブプロセス起動する 2 テストを除外

## 必須基準（全タスク共通）

1. **全テストがパス** — 上記コマンドで failed / error が 0
2. **根本原因の修正** — 対症療法（テスト期待値の書き換え、例外の握り潰し、sleep 追加）で
   ないこと。git diff を読み、失敗原因の発生箇所そのものを変更しているか判定する
3. **デグレなし** — タスクと無関係のファイルが diff に含まれない。テストの削除・skip 追加・
   アサーション弱体化がない（`git diff -- tests/` で確認）
4. **既存パターン準拠** — 下記プロジェクト固有基準および CLAUDE.md に適合

## プロジェクト固有基準

### A. 契約テストの凍結

```bash
git diff --stat -- tests/test_stop_stream_contracts.py tests/test_prepare_environment_contracts.py
# → 出力なし
.venv/bin/python -m pytest tests/test_stop_stream_contracts.py tests/test_prepare_environment_contracts.py -p no:cacheprovider -q
# → green
```

### B. エントリポイントは薄く

新しいドメインロジックは `src/rct/` 配下（`video_library.py`、`obs_client.ensure_media_file`）。
`scripts/gui_app.py` の変更は配線のみであることを diff で判定。

### C. ad-hoc sleep 禁止（2026-05-16 スリープ事故由来）

```bash
git diff -U0 -- scripts/ src/ ':(exclude)src/rct/retry.py' | grep '^+' | grep 'time\.sleep'
# → 出力なし（GUI のポーリングは self.after ループで実装すること）
```

### D. plist テンプレート同期 — **N/A**（本タスクは plist を変更しない）

```bash
git diff -- config/launchd/
# → 出力なし
```

## タスク固有基準

- [ ] **opt-in 保証**: `OBS_MEDIA_FILE_PATH` 未設定時、`start_streaming` の WS 呼び出し列が従来と完全一致
      — 検証: `test_start_streaming_skips_media_file_when_unset` green ＋ 既存 `test_obs_client.py` の頭切れ対策テスト群が**無編集**で green
- [ ] **凍結シーケンス保護**: `ensure_media_file` は `set_current_program_scene` の後、最初の `set_scene_item_enabled`（凍結開始）より前に呼ばれる
      — 検証: `test_start_streaming_ensures_media_file_before_freeze` green
- [ ] **ensure_media_file のフェイルセーフ**: WS エラーで例外を伝播させない（朝の配信継続）
      — 検証: `test_ensure_media_file_returns_none_and_never_raises_on_error` green
- [ ] **dotenv 安全性**: 日本語＋スペースのパスが `.env` ラウンドトリップで壊れない
      — 検証: `test_update_env_values_roundtrips_via_dotenv_with_japanese_and_spaces` green
- [ ] **GUI 動画選択**: videos/ から選択 → `.env` 書込 → OBS 起動中なら即時反映、配信中（output_active）はスキップ
      — 検証: 手動（OBS 起動・配信なしの日中: 選択 → OBS プレビュー切替 → `.env` 反映 → 再適用で「既に設定済み」）
- [ ] **コンテナ伝播**: `docker compose run --rm rct python -c "from rct.settings import settings; print(settings.OBS_MEDIA_FILE_PATH)"` が選択パス（日本語含む）を出力
- [ ] **ショートカット**: `~/Desktop/ラジオ体操管理.app` ダブルクリックでパネル起動、10 秒以内にステータス表示（chdir + Finder PATH 検証）
- [ ] **start_stream.py / launchd 無変更**: `git diff -- scripts/start_stream.py config/launchd/` → 空

## 判定ルール

- 全基準 ✓ で PASS。1 つでも ✗ なら FAIL
- 「該当時のみ」基準は、非該当なら ✓（N/A）と明記する
