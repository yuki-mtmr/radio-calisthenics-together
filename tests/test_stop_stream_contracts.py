"""stop_stream.py の contract テスト (characterization)。

test_stop_stream.py (2026-05-17 回帰) を補完する追加ピン:
- OBS 停止「失敗」(接続 OK・停止 NG) でも SystemExit なし (exit 0) + 翌日予約実行
- 当日残骸枠の削除
- JST→UTC (-9h) 変換とタイトル形式「みんなでラジオ体操 (YYYY/MM/DD HH:MM)」
  (fix_broadcasts の dedup / verify_stream が文字列一致で依存する契約)

ベースライン純度維持のため既存ファイルは編集せず新規ファイルで追加する。
"""
from datetime import datetime
from unittest.mock import MagicMock, patch


def _configure_settings(mock_settings, start_time="06:59", privacy="unlisted"):
    mock_settings.STREAM_START_TIME = start_time
    mock_settings.YOUTUBE_PRIVACY_STATUS = privacy


def test_obs_stop_failure_exits_zero_and_schedules_tomorrow():
    """OBS 接続は成功するが停止コマンドが失敗 → SystemExit なし + 翌日予約は実行。

    既存テストは「接続失敗」のみピン。こちらは「停止失敗」でも
    exit 0 契約 (launchd 視点) が保たれることをピンする。
    """
    with patch("scripts.stop_stream.OBSClient") as mock_obs_class, \
         patch("scripts.stop_stream.YouTubeClient") as mock_yt_class, \
         patch("scripts.stop_stream.settings") as mock_settings:

        mock_obs = MagicMock()
        mock_obs.connect.return_value = True
        mock_obs.stop_streaming.return_value = False  # 停止失敗
        mock_obs_class.return_value = mock_obs

        mock_yt = MagicMock()
        mock_yt.find_broadcast_by_date.return_value = None
        mock_yt_class.return_value = mock_yt

        _configure_settings(mock_settings)

        from scripts.stop_stream import main

        # SystemExit が上がらず None を返す = スクリプトは exit 0
        assert main() is None
        mock_yt.create_broadcast.assert_called_once()


def test_todays_leftover_broadcast_is_deleted():
    """当日の残骸枠が残っていれば削除してから翌日枠を作成する。"""
    with patch("scripts.stop_stream.YouTubeClient") as mock_yt_class, \
         patch("scripts.stop_stream.settings") as mock_settings:

        mock_yt = MagicMock()
        # 1 回目 (今日) は残骸あり、2 回目 (明日) は無し
        mock_yt.find_broadcast_by_date.side_effect = [
            {"id": "today_id", "snippet": {"title": "みんなでラジオ体操 (leftover)"}},
            None,
        ]
        mock_yt_class.return_value = mock_yt

        _configure_settings(mock_settings)

        from scripts.stop_stream import schedule_tomorrow_broadcast

        schedule_tomorrow_broadcast()

        mock_yt.delete_broadcast.assert_called_once_with("today_id")
        mock_yt.create_broadcast.assert_called_once()


def test_jst_to_utc_conversion_and_title_format():
    """翌日枠は JST -9h の UTC ISO 時刻 + 契約タイトル形式で作成される。"""
    fixed_now = datetime(2026, 6, 10, 12, 0, 0)
    with patch("scripts.stop_stream.YouTubeClient") as mock_yt_class, \
         patch("scripts.stop_stream.settings") as mock_settings, \
         patch("scripts.stop_stream.datetime") as mock_dt:

        mock_dt.now.return_value = fixed_now

        mock_yt = MagicMock()
        mock_yt.find_broadcast_by_date.return_value = None
        mock_yt_class.return_value = mock_yt

        _configure_settings(mock_settings, start_time="06:59", privacy="unlisted")

        from scripts.stop_stream import schedule_tomorrow_broadcast

        schedule_tomorrow_broadcast()

        mock_yt.delete_broadcast.assert_not_called()
        args, kwargs = mock_yt.create_broadcast.call_args
        # タイトル契約「みんなでラジオ体操 (YYYY/MM/DD HH:MM)」
        assert args[0] == "みんなでラジオ体操 (2026/06/11 06:59)"
        # JST 06/11 06:59 → UTC 06/10 21:59
        assert kwargs["start_time_iso"] == "2026-06-10T21:59:00Z"
        # privacy_status は settings をそのまま伝搬
        assert kwargs["privacy_status"] == "unlisted"
