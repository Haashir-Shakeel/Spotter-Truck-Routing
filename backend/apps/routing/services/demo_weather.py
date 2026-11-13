"""Synthetic demo weather: clearly labelled storms for walkthroughs, never presented as real.

Live forecasts are often calm, so a demo would rarely show High, Severe, No Travel or missing
data. With ``demo_weather`` on, the trip uses this provider instead of Open-Meteo for both the
route analysis and the corridor slider. Everything downstream (risk engine, load overrides,
risk miles, ranking) is the real code; only the input weather is invented. Responses carry
``weather_source: "demo"`` and a warning, and the UI shows a banner.

Storms are placed relative to the trip's straight line from origin to destination, so they
appear on any trip. Along-track position is a fraction of the trip; cross-track is miles to the
left (+) or right (-) of the direction of travel.

- Wind cell, left of the trip, drifting forward: 58 mph core (No Travel), 48 mph (Severe, and No
  Travel for loads over 30,000 lb), 30 mph edge (Moderate). Hours 0-30.
- Rain band across the trip near two thirds of the way: 0.6 in/hr core (Severe), 0.3 (High),
  0.12 edge (Moderate). Hours 0-18.
- Snow cell right of the trip that forms later: 2.4 in/hr core (Severe), 1.2 (High), 0.6 edge
  (Moderate). Hours 18-40.
- From hour 44 there is no data anywhere, to show how missing forecasts are handled.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from apps.routing.domain.types import Coordinate, HourlyForecast

from .geo import EARTH_RADIUS_MILES, haversine_miles

CALM = (8.0, 0.0, 0.0)  # wind mph, rain in/hr, snow in/hr
NO_DATA_FROM_HOUR = 44


@dataclass(frozen=True, slots=True)
class _Cell:
    along: float  # fraction of the trip at hour 0
    drift_per_hour: float  # fraction of the trip per hour
    across_fraction: float  # cross-track offset as a fraction of trip length (+ left)
    radius_fraction: float  # of trip length
    min_radius_miles: float
    hours: tuple[int, int]  # active from, until (inclusive)
    levels: tuple[tuple[float, float], ...]  # (fraction of radius, value), innermost first


WIND = _Cell(0.35, 0.01, 0.12, 0.12, 25, (0, 30), ((0.4, 58.0), (0.8, 48.0), (1.2, 30.0)))
RAIN = _Cell(0.65, 0.01, -0.02, 0.10, 20, (0, 18), ((0.5, 0.6), (0.8, 0.3), (1.0, 0.12)))
SNOW = _Cell(0.25, 0.0, -0.15, 0.12, 25, (18, 40), ((0.35, 2.4), (0.7, 1.2), (1.0, 0.6)))


def _floor_hour(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


class DemoWeatherProvider:
    def __init__(self, origin: Coordinate, destination: Coordinate, departure_at: datetime) -> None:
        if departure_at.tzinfo is None:
            raise ValueError("Departure time must be timezone-aware.")
        self._origin = origin
        self._start = _floor_hour(departure_at)
        self._length = max(haversine_miles(origin, destination), 1.0)
        mid_lat = math.radians((origin[1] + destination[1]) / 2)
        self._mpd_lat = EARTH_RADIUS_MILES * math.pi / 180
        self._mpd_lon = self._mpd_lat * math.cos(mid_lat)
        dx = (destination[0] - origin[0]) * self._mpd_lon
        dy = (destination[1] - origin[1]) * self._mpd_lat
        norm = math.hypot(dx, dy) or 1.0
        self._ux, self._uy = dx / norm, dy / norm  # unit vector along the trip

    def _trip_frame(self, point: Coordinate) -> tuple[float, float]:
        """(miles along the trip line, miles to its left)."""
        x = (point[0] - self._origin[0]) * self._mpd_lon
        y = (point[1] - self._origin[1]) * self._mpd_lat
        return x * self._ux + y * self._uy, -x * self._uy + y * self._ux

    def _cell_value(self, cell: _Cell, along: float, across: float, hour: float) -> float:
        if not cell.hours[0] <= hour <= cell.hours[1]:
            return 0.0
        center_along = (cell.along + cell.drift_per_hour * hour) * self._length
        center_across = cell.across_fraction * self._length
        radius = max(cell.min_radius_miles, cell.radius_fraction * self._length)
        distance = math.hypot(along - center_along, across - center_across)
        for fraction, value in cell.levels:
            if distance <= fraction * radius:
                return value
        return 0.0

    def conditions(self, point: Coordinate, when: datetime) -> tuple[float, float, float] | None:
        hour = (when - self._start).total_seconds() / 3600
        if hour >= NO_DATA_FROM_HOUR:
            return None
        along, across = self._trip_frame(point)
        return (
            max(CALM[0], self._cell_value(WIND, along, across, hour)),
            self._cell_value(RAIN, along, across, hour),
            self._cell_value(SNOW, along, across, hour),
        )

    def hourly_forecasts(
        self, points: Sequence[Coordinate], start: datetime, end: datetime
    ) -> list[HourlyForecast]:
        first = _floor_hour(start)
        count = int((_floor_hour(end) - first).total_seconds() // 3600) + 1
        times = tuple(first + timedelta(hours=h) for h in range(count))
        forecasts = []
        for lon, lat in points:
            values = [self.conditions((lon, lat), t) for t in times]
            forecasts.append(
                HourlyForecast(
                    lon=lon,
                    lat=lat,
                    times=times,
                    wind_mph=tuple(v[0] if v else None for v in values),
                    rain_in_per_hour=tuple(v[1] if v else None for v in values),
                    snow_in_per_hour=tuple(v[2] if v else None for v in values),
                )
            )
        return forecasts
