#!/usr/bin/env bash
# youtube-autopost (private repo, ローカルにのみ存在) を wheel 化して vendor/ に固定する。
#
# 使い方:
#   ./scripts/update_vendor.sh
#
# youtube-autopost 側でコード変更が入ったら再実行し、生成された vendor/*.whl を
# コミットすること (wheel は git 管理対象。private repo が手元にないと再現不能なため)。
#
# HIGH (vendor wheel の再現性): wheel 生成だけでは .venv に反映されず、
# 「wheel は更新したが .venv は古いまま」というズレが起き得る。
# このスクリプトが .venv への force-reinstall まで行うことで再現性を保証する。
# 生成後は docker compose build も忘れずに実行すること。
set -euo pipefail
cd "$(dirname "$0")/.."

SOURCE_REPO="/Users/yukimatsumori/projects/youtube-autopost"
VENV_PIP=".venv/bin/pip"

if [ ! -d "$SOURCE_REPO" ]; then
  echo "Error: $SOURCE_REPO not found." >&2
  exit 1
fi

rm -f vendor/youtube_autopost-*.whl
mkdir -p vendor
pip wheel --no-deps -w vendor/ "$SOURCE_REPO"
echo "Generated: $(ls vendor/youtube_autopost-*.whl)"

if [ -x "$VENV_PIP" ]; then
  "$VENV_PIP" install --force-reinstall vendor/youtube_autopost-*.whl
  echo "Installed into .venv: $(ls vendor/youtube_autopost-*.whl)"
else
  echo "Warning: $VENV_PIP not found. Skipping .venv install." >&2
  echo "Run manually: .venv/bin/pip install --force-reinstall vendor/youtube_autopost-*.whl" >&2
fi

echo "Remember to also run: docker compose build"
