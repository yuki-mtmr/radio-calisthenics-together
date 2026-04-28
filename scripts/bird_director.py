#!/usr/bin/env python3
"""Bird overlay director.

配信中、一定間隔ごとに乱数判定で OBS の bird overlay ソースを表示し、
アニメーション秒数経過後に非表示に戻す。0回もあり得る純粋ランダム。
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from rct.logger import setup_logger  # noqa: E402
from rct.obs_client import OBSClient  # noqa: E402
from rct.settings import settings  # noqa: E402

logger = setup_logger()


@dataclass(frozen=True)
class BirdConfig:
    scene_name: str
    source_name: str
    probability: float
    interval_sec: float
    show_duration_sec: float
    duration_sec: float


def should_trigger(probability: float, rng: random.Random) -> bool:
    if not 0.0 <= probability <= 1.0:
        raise ValueError(f"probability must be in [0, 1], got {probability}")
    return rng.random() < probability


def plan_schedule(
    duration_sec: float,
    interval_sec: float,
    probability: float,
    seed: int | None = None,
) -> list[float]:
    rng = random.Random(seed)
    fire_times: list[float] = []
    t = 0.0
    while t < duration_sec:
        if should_trigger(probability, rng):
            fire_times.append(t)
        t += interval_sec
    return fire_times


def _show_bird(obs: OBSClient, scene: str, source: str, duration_sec: float) -> None:
    try:
        obs.set_scene_item_enabled(scene, source, True)
        logger.info(f"Bird shown ({source})")
        time.sleep(duration_sec)
    finally:
        try:
            obs.set_scene_item_enabled(scene, source, False)
            logger.info(f"Bird hidden ({source})")
        except Exception as e:
            logger.warning(f"Failed to hide bird: {e}")


def run(config: BirdConfig, rng: random.Random | None = None) -> int:
    rng = rng or random.Random()
    obs = OBSClient()
    if not obs.connect():
        logger.error("Cannot connect to OBS, aborting bird director.")
        return 1

    try:
        obs.set_scene_item_enabled(config.scene_name, config.source_name, False)
    except Exception as e:
        logger.warning(f"Initial hide failed (source may not exist yet): {e}")

    end_at = datetime.now() + timedelta(seconds=config.duration_sec)
    fire_count = 0
    logger.info(
        f"Bird director started. Until {end_at.strftime('%H:%M:%S')}, "
        f"every {config.interval_sec}s with prob={config.probability}"
    )

    while datetime.now() < end_at:
        if should_trigger(config.probability, rng):
            fire_count += 1
            _show_bird(obs, config.scene_name, config.source_name, config.show_duration_sec)
        sleep_left = (end_at - datetime.now()).total_seconds()
        time.sleep(min(config.interval_sec, max(sleep_left, 0)))

    logger.info(f"Bird director finished. Total fires: {fire_count}")
    return 0


def _parse_args(argv: list[str] | None = None) -> BirdConfig:
    parser = argparse.ArgumentParser(description="OBS bird overlay director")
    parser.add_argument(
        "--source",
        default=os.getenv("OBS_BIRD_SOURCE_NAME", "bird_overlay"),
        help="OBS source name to toggle",
    )
    parser.add_argument(
        "--scene",
        default=settings.OBS_SCENE_NAME,
        help="OBS scene name containing the source",
    )
    parser.add_argument(
        "--probability",
        type=float,
        default=float(os.getenv("BIRD_PROBABILITY", "0.15")),
        help="Probability per interval to trigger (0.0-1.0)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=float(os.getenv("BIRD_INTERVAL_SEC", "30")),
        help="Seconds between probability checks",
    )
    parser.add_argument(
        "--show-duration",
        type=float,
        default=float(os.getenv("BIRD_SHOW_DURATION_SEC", "7")),
        help="Seconds to keep the bird visible",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=float(os.getenv("BIRD_DURATION_SEC", "960")),
        help="Total seconds to run the director (default 16 min)",
    )
    args = parser.parse_args(argv)
    return BirdConfig(
        scene_name=args.scene,
        source_name=args.source,
        probability=args.probability,
        interval_sec=args.interval,
        show_duration_sec=args.show_duration,
        duration_sec=args.duration,
    )


def main(argv: list[str] | None = None) -> int:
    config = _parse_args(argv)
    return run(config)


if __name__ == "__main__":
    sys.exit(main())
