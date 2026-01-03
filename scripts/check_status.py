#!/usr/bin/env python3
import sys
import os
import json

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from rct.obs_client import OBSClient

def main():
    client = OBSClient()
    status = client.get_status()

    print("--- Radio Calisthenics Together Status ---")
    print(f"OBS Running:         {'✅ ON' if status['obs_running'] else '❌ OFF'}")
    print(f"WebSocket Connected: {'✅ CONNECTED' if status['websocket_connected'] else '❌ DISCONNECTED'}")
    print(f"Streaming:           {'🔴 LIVE' if status['streaming'] else '⚪️ IDLE'}")
    print(f"Current Scene:       {status['current_scene']}")
    print("------------------------------------------")

if __name__ == "__main__":
    main()
