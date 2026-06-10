"""check_status.py の characterization テスト。

Dockerfile の CMD が `python scripts/check_status.py` のため、
出力形式はコンテナの疎通確認手段としての runtime 契約。
"""
from unittest.mock import MagicMock, patch

import check_status


def _status(connected, streaming, scene="RADIO_TAISO_LOOP"):
    return {"connected": connected, "streaming": streaming, "scene": scene}


def test_prints_connected_and_idle(capsys):
    with patch("check_status.OBSClient") as mock_cls:
        mock_cls.return_value.get_status.return_value = _status(True, False)
        check_status.main()
    out = capsys.readouterr().out
    assert "✅ YES" in out
    assert "⚪️ IDLE" in out
    assert "RADIO_TAISO_LOOP" in out


def test_prints_live_when_streaming(capsys):
    with patch("check_status.OBSClient") as mock_cls:
        mock_cls.return_value.get_status.return_value = _status(True, True)
        check_status.main()
    out = capsys.readouterr().out
    assert "🔴 LIVE" in out


def test_prints_no_when_disconnected(capsys):
    with patch("check_status.OBSClient") as mock_cls:
        mock_cls.return_value.get_status.return_value = _status(False, False, scene="N/A")
        check_status.main()
    out = capsys.readouterr().out
    assert "❌ NO" in out
