import obsws_python as obs
import time
import subprocess
import os
from .logger import setup_logger
from .settings import settings

logger = setup_logger()

MEDIA_BUFFER_WAIT_SEC = 5  # media source restart 後にエンコーダーがバッファ蓄積する時間

class OBSClient:
    def __init__(self):
        self.host = settings.OBS_WS_HOST
        self.port = settings.OBS_WS_PORT
        self.password = settings.OBS_WS_PASSWORD
        self.client = None

    def connect(self):
        if self.client:
            return True
        try:
            self.client = obs.ReqClient(host=self.host, port=self.port, password=self.password, timeout=10)
            self.client.get_version()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to OBS at {self.host}:{self.port} - {e}")
            return False

    def start_streaming(self):
        if not self.connect():
            return False

        try:
            logger.info(f"Preparing scene: {settings.OBS_SCENE_NAME}")
            self.client.set_current_program_scene(settings.OBS_SCENE_NAME)

            # 動画ソースのリセット（上書き対策）
            if settings.OBS_MEDIA_SOURCE_NAME:
                logger.info(f"Force refreshing media source: '{settings.OBS_MEDIA_SOURCE_NAME}'")
                try:
                    # 1. 一旦非表示にして描画を止める
                    self.set_scene_item_enabled(settings.OBS_SCENE_NAME, settings.OBS_MEDIA_SOURCE_NAME, False)
                    time.sleep(0.5)
                    # 2. 再送を開始し、再読み込みさせる
                    self.client.trigger_media_input_action(settings.OBS_MEDIA_SOURCE_NAME, "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART")
                    self.set_scene_item_enabled(settings.OBS_SCENE_NAME, settings.OBS_MEDIA_SOURCE_NAME, True)
                    # 3. エンコーダーがフレームバッファを蓄積するまで待機
                    #    4/30インシデント: 0.012秒で start_stream を呼んで lag 25%, drop 9.7%、
                    #    実効0.5fps しか出ず YouTube に stalled stream と判断され15分後切断
                    logger.info(f"Waiting {MEDIA_BUFFER_WAIT_SEC}s for media buffer to fill...")
                    time.sleep(MEDIA_BUFFER_WAIT_SEC)
                    logger.info("Media source refreshed and restarted.")
                except Exception as e:
                    logger.warning(f"Media refresh failed: {e}")
            else:
                logger.info("No media source specified for restart.")

            status = self.client.get_stream_status()
            if status.output_active:
                logger.warning(
                    "Stream is already active (possibly stale state). "
                    "Forcing stop before restart to avoid stuck reconnect loop."
                )
                try:
                    self.client.stop_stream()
                except Exception as e:
                    logger.warning(f"Force stop failed (continuing): {e}")
                time.sleep(2)

            logger.info("Starting stream output...")
            self.client.start_stream()
            return True
        except Exception as e:
            logger.error(f"Start stream error: {e}")
            return False

    def set_scene(self, scene_name):
        if not self.connect():
            return False
        try:
            self.client.set_current_program_scene(scene_name)
            return True
        except Exception as e:
            logger.error(f"Set scene error: {e}")
            return False

    def set_scene_item_enabled(self, scene_name, source_name, enabled):
        if not self.connect():
            return False
        try:
            resp = self.client.get_scene_item_id(scene_name, source_name)
            scene_item_id = resp.scene_item_id
            self.client.set_scene_item_enabled(scene_name, scene_item_id, enabled)
            return True
        except Exception as e:
            logger.warning(f"Failed to set scene item enabled ({source_name}): {e}")
            raise e

    def stop_streaming(self):
        if not self.connect():
            return False

        try:
            status = self.client.get_stream_status()
            if not status.output_active:
                logger.info("Stream is already stopped.")
                return True

            logger.info("Stopping stream output...")
            try:
                self.client.stop_stream()
            except Exception as e:
                msg = str(e)
                if "501" in msg:
                    logger.warning(
                        f"StopStream returned 501 (output already inactive); treating as success: {e}"
                    )
                    return True
                raise
            return True
        except Exception as e:
            logger.error(f"Stop stream error: {e}")
            return False

    def get_status(self):
        connected = self.connect()
        streaming = False
        scene = "Unknown"

        if connected:
            try:
                status = self.client.get_stream_status()
                streaming = status.output_active
                scene = self.client.get_current_program_scene().current_program_scene_name
            except Exception:
                pass

        return {
            "connected": connected,
            "streaming": streaming,
            "scene": scene
        }

    def disconnect(self):
        if self.client:
            self.client = None
