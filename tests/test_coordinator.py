"""Tests for value parsing in the coordinator."""
from __future__ import annotations

from custom_components.cn_minute_rain.coordinator import parse_values


def test_parse_values_none() -> None:
    assert parse_values(None) == []


def test_parse_values_str_comma() -> None:
    assert parse_values("1,2,3") == [1.0, 2.0, 3.0]


def test_parse_values_str_with_blank_and_spaces() -> None:
    assert parse_values("1,, 2 ,") == [1.0, 2.0]


def test_parse_values_list_mixed() -> None:
    assert parse_values([1, 2.5, "3"]) == [1.0, 2.5, 3.0]


def test_parse_values_invalid_returns_empty() -> None:
    assert parse_values("a,b") == []
    assert parse_values(123) == []
    assert parse_values({"x": 1}) == []
