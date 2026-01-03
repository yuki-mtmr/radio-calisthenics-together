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

if __name__ == '__main__':
    unittest.main()
