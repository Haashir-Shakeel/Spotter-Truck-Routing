"""Weather risk classification from the assessment's wind/rain/snow table and load overrides.

Shared decimal boundaries in the brief (e.g. rain 0.10-0.25 and 0.25-0.50) are resolved with
half-open intervals; the explicit ``>`` No Travel thresholds for rain and snow are kept as stated.
"""

import math

from apps.routing.domain.risk_levels import RiskLevel
from apps.routing.domain.types import RiskAssessment, WeatherConditions

HEAVY_LOAD_NO_TRAVEL_LB = 30_000
HEAVY_LOAD_SEVERE_LB = 40_000


class InvalidWeatherError(ValueError):
    """Weather input is missing, non-finite or physically impossible. Never treat as Low risk."""


def _require_valid(name: str, value: float) -> None:
    if value is None or isinstance(value, bool) or not isinstance(value, int | float):
        raise InvalidWeatherError(f"{name} must be a number, got {value!r}")
    if not math.isfinite(value):
        raise InvalidWeatherError(f"{name} must be finite, got {value!r}")
    if value < 0:
        raise InvalidWeatherError(f"{name} must not be negative, got {value!r}")


def classify_wind_base(wind_mph: float) -> RiskLevel:
    """Wind category from the table alone, before load overrides."""
    if wind_mph >= 55:
        return RiskLevel.NO_TRAVEL
    if wind_mph >= 45:
        return RiskLevel.SEVERE
    if wind_mph >= 35:
        return RiskLevel.HIGH
    if wind_mph >= 25:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def classify_wind(wind_mph: float, load_weight_lb: float) -> RiskLevel:
    base = classify_wind_base(wind_mph)
    if base == RiskLevel.SEVERE and load_weight_lb > HEAVY_LOAD_NO_TRAVEL_LB:
        return RiskLevel.NO_TRAVEL
    if base == RiskLevel.HIGH and load_weight_lb > HEAVY_LOAD_SEVERE_LB:
        return RiskLevel.SEVERE
    return base


def classify_rain(rain_in_per_hour: float) -> RiskLevel:
    if rain_in_per_hour > 1.00:
        return RiskLevel.NO_TRAVEL
    if rain_in_per_hour >= 0.50:
        return RiskLevel.SEVERE
    if rain_in_per_hour >= 0.25:
        return RiskLevel.HIGH
    if rain_in_per_hour >= 0.10:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def classify_snow(snow_in_per_hour: float) -> RiskLevel:
    if snow_in_per_hour > 3.0:
        return RiskLevel.NO_TRAVEL
    if snow_in_per_hour >= 2.0:
        return RiskLevel.SEVERE
    if snow_in_per_hour >= 1.0:
        return RiskLevel.HIGH
    if snow_in_per_hour >= 0.5:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def _load_override_note(wind_mph: float, base: RiskLevel, adjusted: RiskLevel, load: float) -> str:
    threshold = HEAVY_LOAD_NO_TRAVEL_LB if base == RiskLevel.SEVERE else HEAVY_LOAD_SEVERE_LB
    return (
        f"Wind {wind_mph:g} mph with a {load:,.0f} lb load (over {threshold:,} lb) "
        f"raises wind risk from {base.label} to {adjusted.label}."
    )


def assess_conditions(conditions: WeatherConditions, load_weight_lb: float) -> RiskAssessment:
    """Classify each condition, apply load overrides to wind, and take the worst."""
    _require_valid("wind_mph", conditions.wind_mph)
    _require_valid("rain_in_per_hour", conditions.rain_in_per_hour)
    _require_valid("snow_in_per_hour", conditions.snow_in_per_hour)
    if not math.isfinite(load_weight_lb) or load_weight_lb <= 0:
        raise ValueError(f"load_weight_lb must be a positive number, got {load_weight_lb!r}")

    wind_base = classify_wind_base(conditions.wind_mph)
    wind = classify_wind(conditions.wind_mph, load_weight_lb)
    rain = classify_rain(conditions.rain_in_per_hour)
    snow = classify_snow(conditions.snow_in_per_hour)

    override = None
    if wind != wind_base:
        override = _load_override_note(conditions.wind_mph, wind_base, wind, load_weight_lb)

    return RiskAssessment(
        level=max(wind, rain, snow),
        wind=wind,
        rain=rain,
        snow=snow,
        load_override=override,
    )
