"""役割インターフェース (ISP) — 注釈専用。

fat client (YouTubeClient / OBSClient) のクラス分割は行わない (facade 維持、
テストの patch 文字列温存が最優先)。代わりに「呼び出し側が実際に必要とする
役割」を typing.Protocol で記述し、関数シグネチャの注釈にのみ使う。

- structural typing のため、既存クラスはこのモジュールを import せずに適合する
- production コードからの import は注釈目的のみ。import 時副作用なし
"""
from __future__ import annotations

from typing import Protocol


class AlertSink(Protocol):
    """アラート通知の送信口。実体は rct.notify.send_alert_email。"""

    def __call__(self, subject: str, body: str) -> None: ...


class BroadcastLister(Protocol):
    """YouTube 配信枠の参照系。実体は youtube_autopost.YouTubeClient (vendor, rct.youtube.make_youtube_client 経由)。"""

    def list_upcoming_broadcasts(self) -> list[dict]: ...

    def list_active_broadcasts(self) -> list[dict]: ...

    def find_broadcast_by_date(self, date_str: str) -> dict | None: ...


class BroadcastScheduler(Protocol):
    """YouTube 配信枠の作成・削除。実体は youtube_autopost.YouTubeClient (vendor, rct.youtube.make_youtube_client 経由)。"""

    def create_broadcast(
        self,
        title: str,
        description: str,
        start_time_iso: str,
        privacy_status: str = "public",
    ) -> dict: ...

    def delete_broadcast(self, broadcast_id: str) -> None: ...


class StreamBinder(Protocol):
    """YouTube live stream の作成と broadcast への bind。実体は youtube_autopost.YouTubeClient (vendor, rct.youtube.make_youtube_client 経由)。"""

    def create_stream(self, title: str) -> dict: ...

    def bind_broadcast(self, broadcast_id: str, stream_id: str) -> dict: ...


class StreamOutputControl(Protocol):
    """OBS 配信出力の開始/停止と状態取得。実体は OBSClient。"""

    def connect(self) -> bool: ...

    def start_streaming(self) -> bool: ...

    def stop_streaming(self) -> bool: ...

    def get_status(self) -> dict: ...


class SceneControl(Protocol):
    """OBS シーン切替。実体は OBSClient。"""

    def set_scene(self, scene_name: str) -> bool: ...


class MediaControl(Protocol):
    """OBS ソース可視化制御 (メディア/鳥オーバーレイ)。実体は OBSClient。"""

    def set_scene_item_enabled(
        self, scene_name: str, source_name: str, enabled: bool
    ) -> bool: ...
