"""Tests for the rain-tip computation logic."""
from __future__ import annotations

from custom_components.cn_minute_rain.sensor import _compute_tip


def test_compute_tip_empty() -> None:
    tip = _compute_tip([])
    assert tip["state"] == "无雨"
    assert tip["minutes_to_rain"] is None
    assert tip["rain_minutes"] == 0


def test_compute_tip_all_zero() -> None:
    tip = _compute_tip([0, 0, 0])
    assert tip["state"] == "无雨"
    assert tip["minutes_to_rain"] is None


def test_compute_tip_raining_now() -> None:
    # n=3 -> step = ceil(120/3) = 40; first=0, last=2 -> 3*40 = 120 min
    tip = _compute_tip([1, 2, 3])
    assert tip["minutes_to_rain"] == 0
    assert tip["rain_minutes"] == 120
    assert "正在下雨" in tip["state"]


def test_compute_tip_future() -> None:
    # n=4 -> step = 30; first rain index = 2 -> 60 min; last=3 -> 60 min
    tip = _compute_tip([0, 0, 1, 2])
    assert tip["minutes_to_rain"] == 60
    assert tip["rain_minutes"] == 60
    assert "分钟后开始下雨" in tip["state"]
