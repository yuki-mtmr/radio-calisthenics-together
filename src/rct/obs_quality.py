"""OBS ログから配信品質統計 (落ちフレーム率) を解析する。

2026-07-10 14:01 の配信で CPU 競合により OBS のエンコード落ちフレームが 46.7%
に達しカクカクの VOD が公開されたが、既存の監視 (verify_stream = 「live に
なったか」のみ) では検知できなかった。stop_stream_wrapper (host 側) から
呼び出し、OBS ログの Streaming Stop 直前の統計を見て閾値超過ならアラートする。

OBS ログは host 側にのみ存在し Docker コンテナからは見えないため、この
モジュールは host 側で実行される scripts/stop_stream_wrapper.py から使うこと
(コンテナ内の scripts/stop_stream.py には配線しない)。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path

STOP_MARKER = "==== Streaming Stop ===="

DEFAULT_LOG_DIR = "~/Library/Application Support/obs-studio/logs/"
DEFAULT_THRESHOLD_PCT = 5.0

_RENDERING_LAG_RE = re.compile(
    r"Number of lagged frames due to rendering lag/stalls:\s*(\d+)\s*\(([\d.]+)%\)"
)
_ENCODING_SKIP_RE = re.compile(
    r"number of skipped frames due to encoding lag:\s*(\d+)/(\d+)\s*\(([\d.]+)%\)"
)
_TOTAL_FRAMES_RE = re.compile(r"Total frames output:\s*(\d+)")


@dataclass(frozen=True)
class StreamQualityStats:
    """1 配信セッション分の OBS 品質統計。該当する行が無ければ None。"""

    rendering_lag_pct: float | None
    rendering_lag_frames: int | None
    encoding_skip_pct: float | None
    encoding_skip_frames: int | None
    encoding_total_frames: int | None
    total_frames: int | None
    source_log: str | None = None


def _last_session_segment(text: str) -> str:
    """最後の '==== Streaming Stop ====' 直前のセッションに対応する部分文字列を返す。

    ログに複数の配信セッションが含まれる場合 (multi-trigger 再試行等)、
    直前のセッション区切り (前回の Stop マーカー、無ければ先頭) から
    最後の Stop マーカーまでを切り出す。
    """
    idx = text.rfind(STOP_MARKER)
    if idx == -1:
        return text
    prev_idx = text.rfind(STOP_MARKER, 0, idx)
    start = prev_idx if prev_idx != -1 else 0
    return text[start:idx]


def parse_session_stats(text: str) -> StreamQualityStats:
    """OBS ログ全文から最後のセッションの品質統計を抽出する。

    対象行が無ければ該当フィールドは None (欠損を例外にしない)。
    """
    segment = _last_session_segment(text)

    rendering_lag_frames = rendering_lag_pct = None
    for match in _RENDERING_LAG_RE.finditer(segment):
        rendering_lag_frames = int(match.group(1))
        rendering_lag_pct = float(match.group(2))

    encoding_skip_frames = encoding_total_frames = encoding_skip_pct = None
    for match in _ENCODING_SKIP_RE.finditer(segment):
        encoding_skip_frames = int(match.group(1))
        encoding_total_frames = int(match.group(2))
        encoding_skip_pct = float(match.group(3))

    total_frames = None
    for match in _TOTAL_FRAMES_RE.finditer(segment):
        total_frames = int(match.group(1))

    return StreamQualityStats(
        rendering_lag_pct=rendering_lag_pct,
        rendering_lag_frames=rendering_lag_frames,
        encoding_skip_pct=encoding_skip_pct,
        encoding_skip_frames=encoding_skip_frames,
        encoding_total_frames=encoding_total_frames,
        total_frames=total_frames,
    )


def is_quality_degraded(
    stats: StreamQualityStats, threshold: float = DEFAULT_THRESHOLD_PCT
) -> bool:
    """rendering_lag_pct または encoding_skip_pct が閾値を超えていれば True。

    値が None (統計行が無い) の場合はその軸では劣化と判定しない。
    """
    rendering_ng = stats.rendering_lag_pct is not None and stats.rendering_lag_pct > threshold
    encoding_ng = stats.encoding_skip_pct is not None and stats.encoding_skip_pct > threshold
    return rendering_ng or encoding_ng


def find_latest_log_file(log_dir: str | Path = DEFAULT_LOG_DIR) -> Path | None:
    """log_dir 内で最終更新時刻が最も新しいログファイルを返す。無ければ None。"""
    dir_path = Path(log_dir).expanduser()
    if not dir_path.is_dir():
        return None
    log_files = [p for p in dir_path.iterdir() if p.is_file()]
    if not log_files:
        return None
    return max(log_files, key=lambda p: p.stat().st_mtime)


def get_latest_session_quality(
    log_dir: str | Path = DEFAULT_LOG_DIR,
) -> StreamQualityStats | None:
    """最新の OBS ログを読み、最後のセッションの品質統計を返す。

    ログディレクトリ/ファイルが読めない場合は None (launchd 環境でも
    Path.expanduser でホームディレクトリを解決する)。
    """
    log_file = find_latest_log_file(log_dir)
    if log_file is None:
        return None
    try:
        text = log_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    stats = parse_session_stats(text)
    return replace(stats, source_log=log_file.name)
