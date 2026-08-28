"""ディスク空き容量の判定。

2026-08-06 インシデント由来。ホストのディスクが満杯になり
`[Errno 28] No space left on device: 'config/youtube/token.json'` で
YouTube トークン更新・verify・stop が全滅し、配信が一度も live にならず、
翌日枠の予約も実行されなかった。

当時 health_monitor は問題を検知したがアラートを送るだけでフローを止めず、
prepare/start は空き容量を一切見ていなかった。空き容量を独立した検査項目に
昇格させ、critical なら配信前に止められるようにする。
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Callable

BYTES_PER_GB = 1024 ** 3

OK_LEVEL = "ok"
WARN_LEVEL = "warn"
CRITICAL_LEVEL = "critical"

# shutil.disk_usage 互換のシグネチャ (path -> (total, used, free))
UsageFn = Callable[[str], tuple[int, int, int]]


@dataclass(frozen=True)
class DiskStatus:
    """ディスク空き容量の判定結果 (immutable)。"""

    level: str
    free_gb: float
    message: str

    @property
    def is_ok(self) -> bool:
        return self.level == OK_LEVEL

    @property
    def is_critical(self) -> bool:
        return self.level == CRITICAL_LEVEL


def _level_for(free_gb: float, critical_gb: float, warn_gb: float) -> str:
    """閾値「未満」で発火する。閾値ちょうどは 1 段階軽い側に倒す。"""
    if free_gb < critical_gb:
        return CRITICAL_LEVEL
    if free_gb < warn_gb:
        return WARN_LEVEL
    return OK_LEVEL


def check_free_space(
    path: str,
    critical_gb: float,
    warn_gb: float,
    usage_fn: UsageFn | None = None,
) -> DiskStatus:
    """path を含むファイルシステムの空き容量を 3 段階で判定する。

    Args:
        path: 対象パス (このパスが属するボリュームを見る)
        critical_gb: これ未満なら critical (配信フローを止める水準)
        warn_gb: これ未満なら warn (通知するが止めない水準)
        usage_fn: テスト用の注入口。省略時は shutil.disk_usage

    Returns:
        DiskStatus: 判定結果。空き容量が読めない場合は安全側に倒して critical
    """
    probe = usage_fn if usage_fn is not None else shutil.disk_usage

    try:
        _total, _used, free = probe(path)
    except OSError as e:
        return DiskStatus(
            CRITICAL_LEVEL,
            0.0,
            f"ディスク空き容量を取得できません ({path}): {e}",
        )

    free_gb = free / BYTES_PER_GB
    level = _level_for(free_gb, critical_gb, warn_gb)

    if level == OK_LEVEL:
        message = f"ディスク空き容量 {free_gb:.1f}GB ({path})"
    else:
        threshold = critical_gb if level == CRITICAL_LEVEL else warn_gb
        message = (
            f"ディスク空き容量が不足しています: {free_gb:.1f}GB "
            f"(閾値 {threshold}GB 未満 / {level}) ({path})"
        )

    return DiskStatus(level, free_gb, message)
