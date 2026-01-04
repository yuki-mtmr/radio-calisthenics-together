import obsws_python as obs
import time
import subprocess
import os
from .logger import setup_logger
from .settings import settings

logger = setup_logger()

class OBSClient:
    def __init__(self):
        self.host = settings.OBS_WS_HOST
        self.port = settings.OBS_WS_PORT
        self.password = settings.OBS_WS_PASSWORD
        self.client = None

    def is_obs_running(self):
        if os.path.exists('/.dockerenv'):
            # Cannot check host processes from inside Docker.
            # We'll assume it might be running and let connection logic decide.
            return True

        try:
            output = subprocess.check_output(["pgrep", "-x", "obs"])
            return len(output) > 0
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def launch_obs(self):
        if self.is_obs_running():
            logger.info("OBS is already running.")
            return True

        if os.path.exists('/.dockerenv'):
            logger.warning("Running inside Docker. Cannot automatically launch OBS on host Mac.")
            logger.warning("Please ensure OBS Studio is running on your Mac and WebSocket is enabled.")
            # Still try to connect once in case it's already open
            return self.connect()

        logger.info(f"Launching OBS from {settings.OBS_PATH}...")
        try:
            # Launch OBS as a background process
            subprocess.Popen([settings.OBS_PATH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Wait for OBS to start and websocket to be ready
            for i in range(settings.START_RETRIES):
                logger.info(f"Waiting for OBS to start (attempt {i+1}/{settings.START_RETRIES})...")
                time.sleep(settings.RETRY_DELAY)
                if self.connect():
                    logger.info("Successfully connected to OBS WebSocket.")
                    return True

            logger.error("Failed to connect to OBS WebSocket after launching.")
            return False
        except Exception as e:
            logger.error(f"Error launching OBS: {e}")
            return False

    def connect(self):
        try:
            self.client = obs.ReqClient(host=self.host, port=self.port, password=self.password)
            # Test connection by getting version
            self.client.get_version()
            return True
        except Exception as e:
            logger.debug(f"Connection failed: {e}")
            return False

    def start_streaming(self):
        if not self.client:
            if not self.connect():
                logger.error("Could not connect to OBS.")
                return False

        try:
            # Set Scene
            logger.info(f"Setting scene to: {settings.OBS_SCENE_NAME}")
            self.client.set_current_program_scene(settings.OBS_SCENE_NAME)

            # Restart Media (if configured)
            media_source = getattr(settings, 'OBS_MEDIA_SOURCE_NAME', None)
            if media_source:
                logger.info(f"Restarting media source: {media_source}")
                try:
                    self.client.trigger_media_input_action(media_source, "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART")
                except Exception as e:
                    logger.warning(f"Could not restart media source: {e}")

            # Check if already streaming
            status = self.client.get_stream_status()
            if status.output_active:
                logger.warning("Already streaming.")
                return True

            # Start Streaming
            logger.info("Starting stream...")
            self.client.start_stream()

            # Verify
            time.sleep(2)
            status = self.client.get_stream_status()
            if status.output_active:
                logger.info("Stream started successfully.")
                return True
            else:
                logger.error("Stream failed to start.")
                return False
        except Exception as e:
            logger.error(f"Error during start_streaming: {e}")
            return False

    def stop_streaming(self):
        if not self.client:
            if not self.connect():
                logger.error("Could not connect to OBS.")
                return False

        try:
            status = self.client.get_stream_status()
            if not status.output_active:
                logger.info("Not currently streaming.")
                return True

            logger.info("Stopping stream...")
            self.client.stop_stream()
            logger.info("Stream stopped.")
            return True
        except Exception as e:
            logger.error(f"Error during stop_streaming: {e}")
            return False

    def get_status(self):
        running = self.is_obs_running()
        connected = self.connect() if running else False
        streaming = False
        scene = "Unknown"

        if connected:
            try:
                status = self.client.get_stream_status()
                streaming = status.output_active
                scene_info = self.client.get_current_program_scene()
                scene = scene_info.current_program_scene_name
            except Exception:
                pass

        return {
            "obs_running": running,
            "websocket_connected": connected,
            "streaming": streaming,
            "current_scene": scene
        }

    def disconnect(self):
        if self.client:
            self.client = None
