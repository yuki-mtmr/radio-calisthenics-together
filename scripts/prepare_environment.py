#!/usr/bin/env python3
import subprocess
import time
import sys
import os

def log(message):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")

def is_app_running(app_name):
    try:
        # pgrep returns exit code 0 if process found, 1 if not
        subprocess.check_call(["pgrep", "-x", app_name], stdout=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def open_app(app_name):
    log(f"Starting {app_name}...")
    subprocess.run(["open", "-a", app_name], check=True)

def wait_for_docker():
    log("Waiting for Docker to be ready...")
    # Attempt to run a simple docker command to verify connectivity
    retries = 30
    for i in range(retries):
        try:
            subprocess.check_call(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log("Docker is ready.")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            time.sleep(2)
    log("Timed out waiting for Docker.")
    return False

def main():
    log("--- Checking Environment Pre-flight ---")

    # 1. Check Docker
    if not is_app_running("Docker"):
        log("Docker is NOT running.")
        open_app("Docker")
        # Docker takes a while to boot usually
        if wait_for_docker():
            log("Docker started successfully.")
        else:
            log("Warning: Docker might not be fully ready yet.")
    else:
        log("Docker is already running.")
        # Even if running, verify connectivity
        if not wait_for_docker():
             log("Docker process is running but not responding.")


    # 2. Check OBS
    if not is_app_running("OBS"):
        log("OBS is NOT running.")
        open_app("OBS")
        # Give OBS a moment to start
        time.sleep(5)
    else:
        log("OBS is already running.")

    log("--- Environment Preparation Complete ---")

if __name__ == "__main__":
    main()
