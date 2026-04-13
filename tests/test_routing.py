"""Tests for Shelter Finder routing module."""

from __future__ import annotations

import pytest

from custom_components.shelter_finder.routing import (
    calculate_eta_minutes,
    haversine_distance,
)


def test_haversine_same_point() -> None:
    assert haversine_distance(48.85, 2.35, 48.85, 2.35) == 0.0

def test_haversine_known_distance() -> None:
    dist = haversine_distance(48.8566, 2.3522, 48.8014, 2.1301)
    assert 14000 < dist < 18000

def test_haversine_short_distance() -> None:
    dist = haversine_distance(48.8566, 2.3522, 48.8580, 2.3540)
    assert 100 < dist < 300

def test_eta_walking() -> None:
    eta = calculate_eta_minutes(1400, "walking")
    assert 15 < eta < 18

def test_eta_driving() -> None:
    eta = calculate_eta_minutes(1400, "driving")
    assert 2 < eta < 4

def test_eta_zero_distance() -> None:
    assert calculate_eta_minutes(0, "walking") == 0.0

def test_eta_unknown_mode_defaults_walking() -> None:
    eta_unknown = calculate_eta_minutes(1400, "jetpack")
    eta_walking = calculate_eta_minutes(1400, "walking")
    assert eta_unknown == eta_walking
