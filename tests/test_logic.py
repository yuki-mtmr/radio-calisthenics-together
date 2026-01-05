import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from rct.settings import settings

def calculate_next_day_utc(current_jst_time, target_start_time_str):
    # current_jst_time: datetime (JST)
    # target_start_time_str: "HH:MM"

    tomorrow = current_jst_time + timedelta(days=1)
    start_h, start_m = target_start_time_str.split(':')

    # JST target
    next_start_jst = tomorrow.replace(hour=int(start_h), minute=int(start_m), second=0, microsecond=0)

    # UTC conversion
    next_start_utc = next_start_jst - timedelta(hours=9)
    return next_start_utc.isoformat() + 'Z'

def test_next_day_calculation_logic():
    # Test case: 1/5 14:00 (JST) -> Target 07:00 (JST) next day
    now_jst = datetime(2026, 1, 5, 14, 0, 0)
    target_time = "07:00"

    result = calculate_next_day_utc(now_jst, target_time)

    # Expected: 2026-01-06 07:00 (JST) is 2026-01-05 22:00 (UTC)
    assert result == "2026-01-05T22:00:00Z"

    # Test case: 1/5 23:30 (JST) -> Target 07:00 (JST) next day
    now_jst_late = datetime(2026, 1, 5, 23, 30, 0)
    result_late = calculate_next_day_utc(now_jst_late, target_time)
    assert result_late == "2026-01-05T22:00:00Z"

def test_start_delay_setting_consistency():
    # Ensure buffer setting is used correctly for metadata
    # (Just a placeholder to remind that we should maintain these settings)
    assert settings.YOUTUBE_RESERVATION_BUFFER_MINUTES >= 0
