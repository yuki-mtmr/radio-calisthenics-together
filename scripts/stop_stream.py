#!/usr/bin/env python3
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from rct.obs_client import OBSClient
from rct.logger import setup_logger

logger = setup_logger()

def main():
    logger.info("--- Stopping Stream Process ---")
    client = OBSClient()

    if not client.connect():
        logger.error("Could not connect to OBS. It might not be running.")
        sys.exit(0) # Exit gracefully if OBS is already closed

    if client.stop_streaming():
        logger.info("Stop stream sequence completed successfully.")
    else:
        logger.error("Stop stream sequence failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
