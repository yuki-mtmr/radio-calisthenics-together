#!/bin/bash
# OBS を週次で再起動して内部状態の腐敗を予防する。
# 4/3〜4/29 のインシデント: 26日連続稼働で OBS が "streaming中" フラグを保持したまま
# RTMP reconnect ループに入り、毎朝のスクリプトが「already active」で何もしなくなった。
# 週1で kill→open することで腐敗を予防する。

set -u
LOG_FILE="${LOG_FILE:-$(cd "$(dirname "$0")/.." && pwd)/logs/obs_restart.log}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

log "--- OBS restart begin ---"

if pgrep -f "OBS\.app/Contents/MacOS/OBS$" > /dev/null; then
    log "OBS is running, killing..."
    killall OBS 2>>"$LOG_FILE" || log "killall returned non-zero (already gone?)"
    # Wait for full shutdown (max 30s)
    for i in $(seq 1 30); do
        if ! pgrep -f "OBS\.app/Contents/MacOS/OBS$" > /dev/null; then
            log "OBS shut down after ${i}s"
            break
        fi
        sleep 1
    done
else
    log "OBS was not running"
fi

sleep 2
log "Starting OBS..."
open -a OBS
sleep 5

if pgrep -f "OBS\.app/Contents/MacOS/OBS$" > /dev/null; then
    log "OBS started successfully"
    log "--- OBS restart end (OK) ---"
    exit 0
else
    log "ERROR: OBS did not start"
    log "--- OBS restart end (FAIL) ---"
    exit 1
fi
