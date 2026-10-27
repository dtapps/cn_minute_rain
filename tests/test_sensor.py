"""_compute_tip：把强度数组折算成“多少分钟后下雨 / 下多久”的纯逻辑。"""

from __future__ import annotations

import pytest

from custom_components.cn_minute_rain.sensor import _compute_tip


def test_compute_tip_empty() -> None:
    tip = _compute_tip([])
    assert tip["state"] == "无雨"
    assert tip["minutes_to_rain"] is None
    assert tip["rain_minutes"] == 0
    assert tip["icon"] == "mdi:weather-sunny"


def test_compute_tip_all_zero() -> None:
    tip = _compute_tip([0, 0, 0])
    assert tip["state"] == "无雨"
    assert tip["minutes_to_rain"] is None
    assert tip["rain_minutes"] == 0


def test_compute_tip_all_negative_treated_as_no_rain() -> None:
    """接口给异常负值（或全负）时不能拼出“约 -60 分钟后开始下雨”。"""
    tip = _compute_tip([-1.0, -2.0, 0.0])
    assert tip["state"] == "无雨"
    assert tip["minutes_to_rain"] is None
    assert tip["rain_minutes"] == 0


def test_compute_tip_raining_now() -> None:
    # n=3 -> step = ceil(120/3) = 40; first=0, last=2 -> 3*40 = 120 min
    tip = _compute_tip([1, 2, 3])
    assert tip["minutes_to_rain"] == 0
    assert tip["rain_minutes"] == 120
    assert "正在下雨" in tip["state"]
    assert tip["icon"] == "mdi:weather-pouring"


def test_compute_tip_future() -> None:
    # n=4 -> step = 30; first rain index = 2 -> 60 min; last=3 -> 60 min
    tip = _compute_tip([0, 0, 1, 2])
    assert tip["minutes_to_rain"] == 60
    assert tip["rain_minutes"] == 60
    assert "分钟后开始下雨" in tip["state"]
    assert tip["icon"] == "mdi:weather-rainy"


def test_compute_tip_smart_interval_is_rounded_up() -> None:
    """120 不能被 n 整除时 step 必须向上取整（n=7 -> ceil(120/7)=18）。"""
    tip = _compute_tip([0, 0, 0, 1, 2, 3, 0])
    assert tip["minutes_to_rain"] == 3 * 18
    assert tip["rain_minutes"] == 3 * 18


def test_compute_tip_step_never_drops_below_one_minute() -> None:
    """n > 120 时 ceil(120/n) 会算出 0，必须被 max(1, ...) 兜住。"""
    values = [0] * 150
    values[10] = 0.5
    values[11] = 0.5
    tip = _compute_tip(values)

    assert tip["minutes_to_rain"] == 10
    assert tip["rain_minutes"] == 2


def test_compute_tip_single_point() -> None:
    # n=1 -> step = 120
    tip = _compute_tip([3.0])
    assert tip["minutes_to_rain"] == 0
    assert tip["rain_minutes"] == 120


def test_compute_tip_rain_only_at_the_end() -> None:
    # n=4 -> step 30；只有最后一点有雨 -> 90 分钟后开始，持续 30 分钟
    tip = _compute_tip([0, 0, 0, 5])
    assert tip["minutes_to_rain"] == 90
    assert tip["rain_minutes"] == 30


@pytest.mark.parametrize(
    ("values", "expected_minutes", "expected_duration"),
    [
        pytest.param([0, 1, 0], 40, 40, id="single-pulse"),
        pytest.param([1, 0, 0, 1], 0, 120, id="rain-now-with-gap"),
        pytest.param([0.1, 0.2], 0, 120, id="rain-now-two-points"),
        pytest.param([0, 0, 0, 0, 0.3], 96, 24, id="five-points-last-only"),
    ],
)
def test_compute_tip_table(values, expected_minutes, expected_duration) -> None:
    tip = _compute_tip(values)
    assert tip["minutes_to_rain"] == expected_minutes
    assert tip["rain_minutes"] == expected_duration
