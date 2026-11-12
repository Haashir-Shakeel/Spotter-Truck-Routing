"""Hourly forecasts from Open-Meteo, normalized to ``HourlyForecast``.

- Wind: ``wind_speed_10m`` (sustained wind, not gusts) in mph.
- Rain: ``rain + showers`` for the preceding hour, in inches -> in/hr.
- Snow: ``snowfall`` for the preceding hour, in inches -> in/hr.

Units are requested explicitly and verified in the response; anything unexpected is rejected
instead of silently converted. Many points are fetched per request, in batches.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from apps.routing.domain.types import Coordinate, HourlyForecast

from .errors import ProviderResponseError
from .http import get_json

PROVIDER = "Open-Meteo"
HOURLY_FIELDS = ("wind_speed_10m", "rain", "showers", "snowfall")
EXPECTED_UNITS = {
    "wind_speed_10m": {"mp/h", "mph"},
    "rain": {"inch"},
    "showers": {"inch"},
    "snowfall": {"inch"},
}
DEFAULT_BATCH_SIZE = 100


class WeatherProvider(Protocol):
    def hourly_forecasts(
        self, points: Sequence[Coordinate], start: datetime, end: datetime
    ) -> list[HourlyForecast]: ...


def _hour_param(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("Forecast window must be timezone-aware.")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:00")


class OpenMeteoWeatherProvider:
    def __init__(
        self,
        client: httpx.Client,
        base_url: str = "https://api.open-meteo.com/v1",
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_retries: int = 2,
    ) -> None:
        self._client = client
        self._url = f"{base_url.rstrip('/')}/forecast"
        self._batch_size = batch_size
        self._max_retries = max_retries

    def hourly_forecasts(
        self, points: Sequence[Coordinate], start: datetime, end: datetime
    ) -> list[HourlyForecast]:
        """Forecasts for each point (same order) covering whole hours from ``start`` to ``end``."""
        start_hour, end_hour = _hour_param(start), _hour_param(end)  # validates tz-awareness
        if end < start:
            raise ValueError("Forecast window end must not be before start.")
        forecasts: list[HourlyForecast] = []
        for offset in range(0, len(points), self._batch_size):
            batch = points[offset : offset + self._batch_size]
            body = get_json(
                self._client,
                self._url,
                params={
                    "latitude": ",".join(f"{lat:.4f}" for _, lat in batch),
                    "longitude": ",".join(f"{lon:.4f}" for lon, _ in batch),
                    "hourly": ",".join(HOURLY_FIELDS),
                    "wind_speed_unit": "mph",
                    "precipitation_unit": "inch",
                    "timezone": "GMT",
                    "timeformat": "unixtime",
                    "start_hour": start_hour,
                    "end_hour": end_hour,
                },
                provider=PROVIDER,
                max_retries=self._max_retries,
            )
            forecasts.extend(parse_open_meteo(body, batch))
        return forecasts


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ProviderResponseError(PROVIDER, f"non-numeric value {value!r}") from exc
    return number


def _sum_or_none(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else a + b


def _parse_location(location: Any, point: Coordinate) -> HourlyForecast:
    if not isinstance(location, dict):
        raise ProviderResponseError(PROVIDER, "unexpected location shape")
    units = location.get("hourly_units", {})
    for field, allowed in EXPECTED_UNITS.items():
        if units.get(field) not in allowed:
            raise ProviderResponseError(
                PROVIDER, f"unexpected unit for {field}: {units.get(field)!r}"
            )

    hourly = location.get("hourly", {})
    try:
        times = tuple(datetime.fromtimestamp(int(t), tz=UTC) for t in hourly["time"])
        columns = {field: [_optional_float(v) for v in hourly[field]] for field in HOURLY_FIELDS}
    except (KeyError, TypeError, ValueError) as exc:
        raise ProviderResponseError(PROVIDER, "hourly data is malformed") from exc
    if any(len(values) != len(times) for values in columns.values()):
        raise ProviderResponseError(PROVIDER, "hourly series have different lengths")

    lon, lat = point
    return HourlyForecast(
        lon=lon,
        lat=lat,
        times=times,
        wind_mph=tuple(columns["wind_speed_10m"]),
        rain_in_per_hour=tuple(
            _sum_or_none(r, s) for r, s in zip(columns["rain"], columns["showers"], strict=True)
        ),
        snow_in_per_hour=tuple(columns["snowfall"]),
    )


def parse_open_meteo(body: Any, points: Sequence[Coordinate]) -> list[HourlyForecast]:
    """Open-Meteo returns an object for one location and a list for several."""
    locations = [body] if isinstance(body, dict) else body
    if not isinstance(locations, list) or len(locations) != len(points):
        raise ProviderResponseError(PROVIDER, "number of locations does not match the request")
    return [_parse_location(loc, point) for loc, point in zip(locations, points, strict=True)]
