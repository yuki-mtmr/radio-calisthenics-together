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
    print(f"Connected: {'✅ YES' if status['connected'] else '❌ NO'}")
    print(f"Streaming: {'🔴 LIVE' if status['streaming'] else '⚪️ IDLE'}")
    print(f"Scene:     {status['scene']}")
    print("------------------------------------------")

if __name__ == "__main__":
    main()
