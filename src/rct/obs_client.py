import obsws_python as obs
import time
import subprocess
import os
from .logger import setup_logger
from .settings import settings

logger = setup_logger()

MEDIA_BUFFER_WAIT_SEC = 5  # media source restart 後にエンコーダーがバッファ蓄積する時間
MEDIA_CURSOR_TOLERANCE_MS = 500  # warmup 後に許容する再生位置のズレ（これを超えたら再凍結）
RESTART_SETTLE_SEC = 0.5  # RESTART(非同期)が落ち着くまでの待機。これが無いと PAUSE が再生に負ける（実機確認）

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

    def _prepare_scene(self) -> None:
        """配信シーンを切り替える。"""
        logger.info(f"Preparing scene: {settings.OBS_SCENE_NAME}")
        self.client.set_current_program_scene(settings.OBS_SCENE_NAME)

    def _refresh_and_freeze_media(self, source: str) -> None:
        """メディアソースを位置0で凍結しバッファを蓄積する。

        手順: 非表示 → 表示 (restart_on_activate) → RESTART→PAUSE で凍結
        → MEDIA_BUFFER_WAIT_SEC 待機 → 位置検証。
        4/30・5/1 インシデント対応コメントは _freeze_media_at_zero 参照。
        """
        logger.info(f"Force refreshing media source: '{source}'")
        try:
            # 1. 一旦非表示にして描画を止める
            self.set_scene_item_enabled(settings.OBS_SCENE_NAME, source, False)
            time.sleep(0.5)
            # 2. 先に表示（アクティブ化）。restart_on_activate でここで位置0から自動再生。
            self.set_scene_item_enabled(settings.OBS_SCENE_NAME, source, True)
            time.sleep(0.3)
            # 3. 位置0で確実に凍結 (RESTART→待機→PAUSE→cursor0)
            self._freeze_media_at_zero(source)
            # 4. エンコーダーがフレームバッファを蓄積するまで待機
            # 4/30インシデント: 0.012秒で start_stream → lag 25%, drop 9.7%, 実効0.5fps
            logger.info(f"Waiting {MEDIA_BUFFER_WAIT_SEC}s for media buffer to fill (paused at position 0)...")
            time.sleep(MEDIA_BUFFER_WAIT_SEC)
            # 5. 実再生位置を検証、ズレていたら再凍結
            self._ensure_media_paused_at_zero(source)
            logger.info("Media source refreshed and paused at position 0.")
        except Exception as e:
            logger.warning(f"Media refresh failed: {e}")

    def _force_stop_if_stale(self) -> None:
        """stale な配信出力があれば強制停止する。

        4/25インシデント: OBS が output_active=True のまま reconnect ループに陥り
        旧実装が start を呼ばなかった → 新 broadcast に送出されなかった。
        """
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

    def start_streaming(self, resume_media: bool = True):
        if not self.connect():
            return False

        try:
            self._prepare_scene()

            if settings.OBS_MEDIA_SOURCE_NAME:
                self._refresh_and_freeze_media(settings.OBS_MEDIA_SOURCE_NAME)
            else:
                logger.info("No media source specified for restart.")

            self._force_stop_if_stale()

            logger.info("Starting stream output...")
            self.client.start_stream()

            # resume_media=True (デフォルト) の場合のみ PLAY を送出する。
            # False の場合は定刻アンカー方式で呼び出し側が resume_media_playback() を呼ぶ。
            if settings.OBS_MEDIA_SOURCE_NAME and resume_media:
                time.sleep(0.5)  # ストリームが安定するまで少し待つ
                try:
                    self.client.trigger_media_input_action(
                        settings.OBS_MEDIA_SOURCE_NAME,
                        "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY"
                    )
                    logger.info("Media playback resumed from position 0.")
                except Exception as e:
                    logger.warning(f"Media play resume failed: {e}")
            return True
        except Exception as e:
            logger.error(f"Start stream error: {e}")
            return False

    def _freeze_media_at_zero(self, source: str) -> None:
        """メディアソースを位置0で確実に静止させる。

        OBS の RESTART アクションは非同期で、直後に PAUSE を送ると RESTART の
        「位置0から再生開始」に PAUSE が負けて再生が止まらない（OBS 28系で実機確認:
        state=PAUSED のまま cursor が実時間で進む）。RESTART→待機→PAUSE の順にし、
        さらに set_media_input_cursor で位置を厳密に0へ寄せる。
        """
        self.client.trigger_media_input_action(source, "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART")
        time.sleep(RESTART_SETTLE_SEC)
        self.client.trigger_media_input_action(source, "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE")
        try:
            self.client.set_media_input_cursor(source, 0)
        except Exception as e:
            logger.warning(f"set_media_input_cursor failed (continuing): {e}")

    def _media_cursor_ms(self, source: str):
        """メディアソースの現在再生位置(ms)を返す。取得不能/不明なら None。"""
        try:
            st = self.client.get_media_input_status(source)
        except Exception as e:
            logger.warning(f"get_media_input_status failed: {e}")
            return None
        raw = getattr(st, "media_cursor", None)
        if isinstance(raw, (int, float)) and raw >= 0:
            return int(raw)
        return None

    def _ensure_media_paused_at_zero(self, source: str, retries: int = 2) -> None:
        """warmup 後、実再生位置が位置0付近で静止しているか OBS に問い合わせて検証する。

        restart_on_activate などで動画が進んでしまった場合に備え、ズレ(>許容値)を
        検知したら _freeze_media_at_zero で再凍結する（最大 retries+1 回）。位置が
        取得できない場合はガードをスキップする（凍結処理で根本対応済みのため fail-safe）。
        """
        for attempt in range(retries + 1):
            cursor = self._media_cursor_ms(source)
            if cursor is None:
                logger.warning("Media position unknown; skipping position guard.")
                return
            if cursor <= MEDIA_CURSOR_TOLERANCE_MS:
                logger.info(f"Media verified paused at {cursor}ms (<= {MEDIA_CURSOR_TOLERANCE_MS}ms).")
                return
            logger.warning(
                f"Media drifted to {cursor}ms before stream start; "
                f"re-freezing at position 0 (attempt {attempt + 1}/{retries + 1})."
            )
            self._freeze_media_at_zero(source)
        logger.error(
            f"Media still drifted after {retries + 1} attempts; proceeding (head may be slightly cut)."
        )

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

    def resume_media_playback(self, source_name: str) -> bool:
        """位置0からの再生を開始する (定刻アンカー方式で定刻に呼び出す)。"""
        try:
            if not self.connect():
                return False
            self.client.trigger_media_input_action(
                source_name,
                "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY"
            )
            logger.info("Media playback resumed from position 0.")
            return True
        except Exception as e:
            logger.warning(f"Media play resume failed: {e}")
            return False

    def disconnect(self):
        if self.client:
            self.client = None
