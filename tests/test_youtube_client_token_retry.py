"""youtube_client のトークン更新リトライ contract テスト。

5×30s リトライ + 失敗時アラート + 新規認証 fallback は 2026-05 障害対応の中核。
P4 で retry 基盤 (rct.retry) へ委譲する際の互換ピンとして、回数・間隔・
アラート内容を凍結する。

注意: アラート本文中の絶対パス行 (cd /Users/...) は P4 で動的化予定のため
ピンしない。件名・再認証スクリプト名・リトライ回数表記のみ契約とする。

既存 test_youtube_client.py は time.sleep を patch しないため実時間で
リトライ待機する。本ファイルのテストは全て sleep を patch して高速に保つ。
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, mock_open, patch

from google.auth.exceptions import RefreshError

import rct.youtube_client as yc
from rct.youtube_client import YouTubeClient


def test_retry_constants_are_incident_tuned_values():
    """5 回 × 30 秒は事故対応で調整済みの凍結値 (DO NOT リスト対象)。"""
    assert yc.TOKEN_REFRESH_MAX_RETRIES == 5
    assert yc.TOKEN_REFRESH_RETRY_DELAY == 30


def _expired_creds():
    creds = MagicMock()
    creds.valid = False
    creds.expired = True
    creds.refresh_token = "some_refresh_token"
    return creds


def test_refresh_failure_retries_5_times_sleeping_30s_between():
    """リフレッシュ全滅: refresh 5 回呼び出し、間の sleep は 30s × 4 回のみ。"""
    expired = _expired_creds()
    expired.refresh.side_effect = RefreshError("Token has been expired or revoked.")

    new_creds = MagicMock()
    new_creds.valid = True
    new_creds.expiry = datetime.utcnow() + timedelta(days=30)

    with patch("rct.youtube_client.build"), \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open()), \
         patch("pickle.load", return_value=expired), \
         patch("pickle.dump"), \
         patch("rct.youtube_client.InstalledAppFlow") as mock_flow, \
         patch("rct.youtube_client.send_alert_email") as mock_alert, \
         patch("rct.youtube_client.time.sleep") as mock_sleep:

        mock_flow.from_client_secrets_file.return_value.run_local_server.return_value = new_creds

        YouTubeClient()

        assert expired.refresh.call_count == 5
        # 最終試行の後には sleep しない (4 回のみ)
        assert [c[0][0] for c in mock_sleep.call_args_list] == [30, 30, 30, 30]
        mock_alert.assert_called_once()


def test_refresh_success_midway_stops_retrying_without_alert():
    """3 回目で成功 → それ以上リトライせず、アラートも新規認証も走らない。"""
    expired = _expired_creds()
    state = {"n": 0}

    def refresh_side_effect(request):
        state["n"] += 1
        if state["n"] < 3:
            raise RefreshError(f"fail {state['n']}")
        expired.valid = True
        expired.expiry = datetime.utcnow() + timedelta(hours=1)

    expired.refresh.side_effect = refresh_side_effect

    with patch("rct.youtube_client.build"), \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open()), \
         patch("pickle.dump"), \
         patch("pickle.load", return_value=expired), \
         patch("rct.youtube_client.InstalledAppFlow") as mock_flow, \
         patch("rct.youtube_client.send_alert_email") as mock_alert, \
         patch("rct.youtube_client.time.sleep") as mock_sleep:

        YouTubeClient()

        assert expired.refresh.call_count == 3
        assert [c[0][0] for c in mock_sleep.call_args_list] == [30, 30]
        mock_alert.assert_not_called()
        mock_flow.from_client_secrets_file.assert_not_called()


def test_refresh_exhaustion_alert_content_and_new_auth_fallback():
    """全滅時: 件名は完全一致、本文に再認証手順、その後新規認証へフォールバック。"""
    expired = _expired_creds()
    expired.refresh.side_effect = RefreshError("Token has been expired or revoked.")

    new_creds = MagicMock()
    new_creds.valid = True
    new_creds.expiry = datetime.utcnow() + timedelta(days=30)

    with patch("rct.youtube_client.build"), \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open()), \
         patch("pickle.load", return_value=expired), \
         patch("pickle.dump") as mock_dump, \
         patch("rct.youtube_client.InstalledAppFlow") as mock_flow, \
         patch("rct.youtube_client.send_alert_email") as mock_alert, \
         patch("rct.youtube_client.time.sleep"):

        mock_flow.from_client_secrets_file.return_value.run_local_server.return_value = new_creds

        YouTubeClient()

        subject, body = mock_alert.call_args[0][0], mock_alert.call_args[0][1]
        assert subject == "Token Refresh Failed"  # アラート件名は凍結契約
        assert "5回" in body
        assert "再認証" in body
        assert "scripts/authenticate_youtube.py" in body
        # 新規認証フローへフォールバックし、新 creds が保存される
        mock_flow.from_client_secrets_file.assert_called_once()
        mock_flow.from_client_secrets_file.return_value.run_local_server.assert_called_once()
        mock_dump.assert_called()
