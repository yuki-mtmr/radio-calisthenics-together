import random
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))

import pytest

from bird_director import should_trigger, plan_schedule


def test_should_trigger_returns_true_when_random_below_probability():
    rng = random.Random()
    rng.random = lambda: 0.05  # type: ignore[method-assign]
    assert should_trigger(probability=0.15, rng=rng) is True


def test_should_trigger_returns_false_when_random_above_probability():
    rng = random.Random()
    rng.random = lambda: 0.5  # type: ignore[method-assign]
    assert should_trigger(probability=0.15, rng=rng) is False


def test_should_trigger_boundary_inclusive_lower():
    rng = random.Random()
    rng.random = lambda: 0.0  # type: ignore[method-assign]
    assert should_trigger(probability=0.15, rng=rng) is True


def test_should_trigger_boundary_exclusive_upper():
    rng = random.Random()
    rng.random = lambda: 0.15  # type: ignore[method-assign]
    assert should_trigger(probability=0.15, rng=rng) is False


def test_should_trigger_zero_probability_never_fires():
    rng = random.Random(0)
    assert all(should_trigger(probability=0.0, rng=rng) is False for _ in range(50))


def test_should_trigger_full_probability_always_fires():
    rng = random.Random(0)
    assert all(should_trigger(probability=1.0, rng=rng) is True for _ in range(50))


def test_should_trigger_invalid_probability_raises():
    rng = random.Random(0)
    with pytest.raises(ValueError):
        should_trigger(probability=-0.1, rng=rng)
    with pytest.raises(ValueError):
        should_trigger(probability=1.1, rng=rng)


def test_plan_schedule_uses_seed_for_reproducibility():
    plan_a = plan_schedule(duration_sec=600, interval_sec=30, probability=0.3, seed=42)
    plan_b = plan_schedule(duration_sec=600, interval_sec=30, probability=0.3, seed=42)
    assert plan_a == plan_b


def test_plan_schedule_count_within_expected_range():
    plan = plan_schedule(duration_sec=900, interval_sec=30, probability=0.15, seed=1)
    assert 0 <= len(plan) <= 30
    assert all(0 <= t < 900 for t in plan)
