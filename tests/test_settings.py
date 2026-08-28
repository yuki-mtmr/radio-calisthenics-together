import sys
import os
import unittest

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from rct.settings import settings

class TestSettings(unittest.TestCase):
    def test_settings_load(self):
        # Even without .env, it should have defaults
        self.assertIsNotNone(settings.OBS_WS_HOST)
        self.assertIsInstance(settings.OBS_WS_PORT, int)

# ---------------------------------------- OBS_MEDIA_FILE_PATH (動画選択機能)


def test_load_settings_obs_media_file_path_set():
    from rct.settings import load_settings
    s = load_settings({"OBS_MEDIA_FILE_PATH": "/host/videos/a.mp4"})
    assert s.OBS_MEDIA_FILE_PATH == "/host/videos/a.mp4"


def test_load_settings_obs_media_file_path_defaults_to_none():
    from rct.settings import load_settings
    assert load_settings({}).OBS_MEDIA_FILE_PATH is None


def test_load_settings_obs_media_file_path_empty_string_is_none():
    """空文字は None 扱い (= 動画差し替え機能の kill switch)。_opt の規約に従う。"""
    from rct.settings import load_settings
    assert load_settings({"OBS_MEDIA_FILE_PATH": ""}).OBS_MEDIA_FILE_PATH is None


# ---------------------------------------- ディスク容量ガード (2026-08-06 ENOSPC 事故)


def test_load_settings_disk_thresholds_default():
    from rct.settings import load_settings
    s = load_settings({})
    assert s.DISK_FREE_CRITICAL_GB == 5
    assert s.DISK_FREE_WARN_GB == 20


def test_load_settings_disk_thresholds_overridable():
    from rct.settings import load_settings
    s = load_settings({"DISK_FREE_CRITICAL_GB": "10", "DISK_FREE_WARN_GB": "50"})
    assert s.DISK_FREE_CRITICAL_GB == 10
    assert s.DISK_FREE_WARN_GB == 50


if __name__ == '__main__':
    unittest.main()
