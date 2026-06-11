#!/bin/bash
# デスクトップに管理パネル起動用の .app バンドルを生成する（冪等・再実行可）。
# Finder 起動アプリは PATH/CWD が最小なため、launcher 内で cd してから venv_gui で起動する。
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP="$HOME/Desktop/ラジオ体操管理.app"

mkdir -p "$APP/Contents/MacOS"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>ラジオ体操管理</string>
    <key>CFBundleDisplayName</key>
    <string>ラジオ体操管理</string>
    <key>CFBundleIdentifier</key>
    <string>jp.radio-calisthenics-together.gui</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
</dict>
</plist>
PLIST

# REPO_DIR は生成時に絶対パスで焼き込む（リポジトリ移動時は本スクリプトを再実行）
cat > "$APP/Contents/MacOS/launcher" <<LAUNCHER
#!/bin/zsh
cd "$REPO_DIR"
exec "$REPO_DIR/venv_gui/bin/python" "$REPO_DIR/scripts/gui_app.py"
LAUNCHER

chmod +x "$APP/Contents/MacOS/launcher"
touch "$APP"  # Finder にバンドル更新を認識させる

echo "作成完了: $APP"
echo "リポジトリを移動した場合は本スクリプトを再実行してください。"
