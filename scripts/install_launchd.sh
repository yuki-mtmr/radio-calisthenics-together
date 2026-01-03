#!/bin/bash

# Configuration
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_DIR="$REPO_DIR/config/launchd"
AGENT_DIR="$HOME/Library/LaunchAgents"

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$AGENT_DIR"

# Template replacements and copy
for plist in "$PLIST_DIR"/*.plist; do
    filename=$(basename "$plist")
    target="$AGENT_DIR/$filename"

    echo "Installing $filename to $target..."

    # Replace placeholders with absolute paths
    sed "s|{{REPO_DIR}}|$REPO_DIR|g" "$plist" > "$target"
    sed -i '' "s|{{USER}}|$USER|g" "$target"

    # Unload if already loaded
    launchctl unload "$target" 2>/dev/null

    # Load and enable
    launchctl load "$target"
    echo "Loaded $filename"
done

echo "Installation complete. use 'launchctl list | grep radio' to verify."
