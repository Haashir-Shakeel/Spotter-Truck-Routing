import math

import pytest

from apps.routing.domain.risk_levels import RiskLevel
from apps.routing.domain.types import WeatherConditions
from apps.routing.services.risk_engine import (
    InvalidWeatherError,
    assess_conditions,
    classify_rain,
    classify_snow,
    classify_wind,
)

L, M, H, S, NT = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)
LIGHT_LOAD = 10_000


def calm(**overrides: object) -> WeatherConditions:
    values = {"wind_mph": 0.0, "rain_in_per_hour": 0.0, "snow_in_per_hour": 0.0, **overrides}
    return WeatherConditions(**values)


@pytest.mark.parametrize(
    ("wind", "expected"),
    [(0, L), (24.999, L), (25, M), (34.9, M), (35, H), (44.9, H), (45, S), (54.9, S), (55, NT)],
)
def test_wind_table_without_load_override(wind: float, expected: RiskLevel) -> None:
    assert classify_wind(wind, LIGHT_LOAD) == expected


@pytest.mark.parametrize(
    ("wind", "load", "expected"),
    [
        (35, 40_000, H),
        (35, 40_001, S),
        (44.9, 45_000, S),
        (45, 30_000, S),
        (45, 30_001, NT),
        (54.9, 80_000, NT),
        (55, 1, NT),
        (34.9, 80_000, M),  # overrides only apply inside their wind bands
    ],
)
def test_wind_load_overrides(wind: float, load: float, expected: RiskLevel) -> None:
    assert classify_wind(wind, load) == expected


@pytest.mark.parametrize(
    ("rain", "expected"),
    [
        (0, L),
        (0.099, L),
        (0.10, M),
        (0.249, M),
        (0.25, H),
        (0.49, H),
        (0.50, S),
        (1.00, S),
        (1.001, NT),
    ],
)
def test_rain_boundaries(rain: float, expected: RiskLevel) -> None:
    assert classify_rain(rain) == expected


@pytest.mark.parametrize(
    ("snow", "expected"),
    [
        (0, L),
        (0.49, L),
        (0.50, M),
        (0.99, M),
        (1.00, H),
        (1.99, H),
        (2.00, S),
        (3.00, S),
        (3.001, NT),
    ],
)
def test_snow_boundaries(snow: float, expected: RiskLevel) -> None:
    assert classify_snow(snow) == expected


def test_highest_condition_wins() -> None:
    result = assess_conditions(
        calm(wind_mph=26, rain_in_per_hour=0.3, snow_in_per_hour=0.6), 20_000
    )

    assert (result.wind, result.rain, result.snow) == (M, H, M)
    assert result.level == H
    assert result.load_override is None


def test_load_override_is_explained() -> None:
    result = assess_conditions(calm(wind_mph=47), 35_000)

    assert result.level == NT
    assert result.load_override is not None
    assert "35,000 lb" in result.load_override
    assert "Severe to No Travel" in result.load_override


@pytest.mark.parametrize("bad", [math.nan, math.inf, -0.1, None, "5"])
@pytest.mark.parametrize("field", ["wind_mph", "rain_in_per_hour", "snow_in_per_hour"])
def test_invalid_weather_is_rejected_not_low(field: str, bad: object) -> None:
    with pytest.raises(InvalidWeatherError):
        assess_conditions(calm(**{field: bad}), LIGHT_LOAD)


@pytest.mark.parametrize("load", [0, -1, math.nan])
def test_invalid_load_is_rejected(load: float) -> None:
    with pytest.raises(ValueError):
        assess_conditions(calm(), load)
