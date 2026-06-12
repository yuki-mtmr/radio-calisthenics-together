# ルーブリック: extract-studio (生成系の分離 — player 側)

> コンテンツ生成系を ../radio-calisthenics-studio へ抽出した後、このリポジトリが
> 純粋な配信プレイヤーとして健全であることを検証する。
> 対象ブランチ: refactor/extract-studio (コミット 2 分割: メタデータ表示 / 分離)

## 検証コマンド(正)

```bash
.venv/bin/python -m pytest tests/ -p no:cacheprovider -q
```

(分離後の新コマンド。`--ignore` と `-m "not slow"` は対象テストの退去により不要)

## 必須基準

1. **全テストがパス** — 上記コマンドで **277 passed, 0 deselected**、failed/error 0
2. **デグレなし** — `git diff main..HEAD -- tests/` に削除されたアサーションの弱体化がない
   (テストファイル削除 3 件 = test_apply_bvh_to_vrm / test_smpl_to_bvh / test_wham_setup と
   test_p7 の full_body 2 テスト削除は studio への**移設**であり、studio 側に同等テストが存在する)

## タスク固有基準

- [ ] 契約テスト凍結 — 検証: `git diff main..HEAD --stat -- tests/test_stop_stream_contracts.py tests/test_prepare_environment_contracts.py` → 出力なし
- [ ] 配信経路の不変 — 検証: `git diff main..HEAD --name-only -- src/rct/obs_client.py scripts/start_stream.py config/launchd/` → 0 件
- [ ] 追跡 16 ファイルの削除がコミットに記録 — 検証: `git diff main..HEAD --diff-filter=D --name-only | wc -l` → 16
- [ ] gui_app が import 可能 — 検証: `.venv/bin/python -m py_compile scripts/gui_app.py` → exit 0
- [ ] media_probe が generation に依存しない — 検証: `grep -rn "rct.generation\|generation\." src/rct/media_probe.py` → import 行なし(`rct.command_runner` のみ)
- [ ] 検証コマンドのメンテ — 検証: `grep -c "not slow" docs/rubrics/feature.md .claude/agents/verifier.md` → feature.md は説明文中の言及のみ、verifier.md のフォールバックコマンドは新形式
- [ ] working tree クリーン(本ルーブリック自身を除く) — 検証: `git status --short` → 本ファイル以外なし
- [ ] Docker スイート green — 検証: 実行済み記録 277 passed (2026-06-12)。再実行は任意(約 4 分半)

## 判定ルール

- 全基準 ✓ で PASS。1 つでも ✗ なら FAIL
