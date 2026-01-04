#!/usr/bin/env python3
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from rct.obs_client import OBSClient
from rct.logger import setup_logger

logger = setup_logger()

def main():
    logger.info("--- Starting Stream Process ---")
    client = OBSClient()

    if client.start_streaming():
        logger.info("Stream started successfully.")
    else:
        logger.error("Start stream sequence failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
