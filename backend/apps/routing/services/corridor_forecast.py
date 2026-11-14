"""Weather risk across the whole trip corridor, hour by hour, for the 0-48 h forecast slider.

This is a different time model from route analysis. Route risk evaluates each checkpoint at the
truck's ETA; the corridor view shows every sample point at one *forecast hour* (departure + h).

Grid:
- A regular grid in miles, not degrees: rows are ``spacing`` miles apart in latitude and each
  row's longitude step is widened by 1/cos(latitude), so samples stay evenly spaced on the
  ground and the heatmap does not show sample density as severity.
- Only grid points within ``buffer`` miles of any route are kept (an envelope, not a bounding
  box). The spacing is widened until the grid fits ``max_points``, which caps provider load
  for long trips.
- Each point/hour is classified with the same risk engine and load rules as the routes. Missing
  data stays ``None``; it is never shown as Low.
"""

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from apps.routing.domain.risk_levels import RiskLevel
from apps.routing.domain.types import Coordinate

from .geo import EARTH_RADIUS_MILES, cumulative_distances_miles, haversine_miles, point_at_distance
from .risk_engine import InvalidWeatherError, assess_conditions
from .weather_interpolation import conditions_at
from .weather_provider import WeatherProvider

logger = logging.getLogger(__name__)

FORECAST_HOURS = 48  # slider covers hours 0..48 inclusive
DEFAULT_SPACING_MILES = 15.0
DEFAULT_BUFFER_MILES = 20.0
DEFAULT_MAX_POINTS = 300
_SPACING_GROWTH = 1.25
_MAX_GROWTH_STEPS = 20
_MILES_PER_DEGREE_LAT = EARTH_RADIUS_MILES * math.pi / 180
_COORD_DECIMALS = 4


@dataclass(frozen=True, slots=True)
class CorridorGrid:
    points: list[Coordinate]
    spacing_miles: float
    buffer_miles: float


@dataclass(frozen=True, slots=True)
class CorridorForecast:
    grid: CorridorGrid
    start_at: datetime
    # risk[hour][point]: RiskLevel, or None when the forecast is unavailable there
    risk: list[list[RiskLevel | None]]

    @property
    def hour_count(self) -> int:
        return len(self.risk)


def _route_anchors(route: Sequence[Coordinate], step_miles: float) -> list[Coordinate]:
    """Points along a route every ``step_miles`` (plus both ends)."""
    cumulative = cumulative_distances_miles(route)
    total = cumulative[-1]
    count = max(1, math.ceil(total / step_miles))
    return [point_at_distance(route, cumulative, total * i / count) for i in range(count + 1)]


def _grid_for_spacing(
    anchors: Sequence[Coordinate], spacing: float, buffer: float, origin: Coordinate
) -> list[Coordinate]:
    lon0, lat0 = origin
    dlat = spacing / _MILES_PER_DEGREE_LAT
    reach_lat = (buffer + spacing) / _MILES_PER_DEGREE_LAT
    cells: dict[tuple[int, int], Coordinate] = {}
    for lon, lat in anchors:
        first_row = math.floor((lat - reach_lat - lat0) / dlat)
        last_row = math.ceil((lat + reach_lat - lat0) / dlat)
        for row in range(first_row, last_row + 1):
            row_lat = lat0 + row * dlat
            if not -85 < row_lat < 85:
                continue
            miles_per_degree_lon = _MILES_PER_DEGREE_LAT * math.cos(math.radians(row_lat))
            dlon = spacing / miles_per_degree_lon
            reach_lon = (buffer + spacing) / miles_per_degree_lon
            # Stagger alternate rows by half a step: a triangular lattice is more uniform.
            offset = 0.5 * dlon if row % 2 else 0.0
            first = math.floor((lon - reach_lon - lon0 - offset) / dlon)
            last = math.ceil((lon + reach_lon - lon0 - offset) / dlon)
            for col in range(first, last + 1):
                if (row, col) in cells:
                    continue
                point = (lon0 + offset + col * dlon, row_lat)
                if haversine_miles(point, (lon, lat)) <= buffer:
                    cells[(row, col)] = (
                        round(point[0], _COORD_DECIMALS),
                        round(point[1], _COORD_DECIMALS),
                    )
    return [cells[key] for key in sorted(cells)]


def build_corridor_grid(
    routes: Sequence[Sequence[Coordinate]],
    *,
    spacing_miles: float = DEFAULT_SPACING_MILES,
    buffer_miles: float = DEFAULT_BUFFER_MILES,
    max_points: int = DEFAULT_MAX_POINTS,
) -> CorridorGrid:
    if not routes or any(len(route) < 2 for route in routes):
        raise ValueError("Each route needs at least two coordinates.")
    if spacing_miles <= 0 or buffer_miles < 0 or max_points < 1:
        raise ValueError("Spacing and max_points must be positive and buffer not negative.")

    # Fixed grid origin (south-west corner) so the same trip always yields the same grid.
    all_points = [c for route in routes for c in route]
    origin = (min(lon for lon, _ in all_points), min(lat for _, lat in all_points))

    spacing = spacing_miles
    for _ in range(_MAX_GROWTH_STEPS):
        # Anchors closer than half the spacing keep the envelope edge accurate to ~spacing/4.
        anchors = [a for route in routes for a in _route_anchors(route, spacing / 2)]
        points = _grid_for_spacing(anchors, spacing, buffer_miles, origin)
        if len(points) <= max_points:
            return CorridorGrid(points, round(spacing, 2), buffer_miles)
        spacing *= _SPACING_GROWTH
    raise ValueError("Corridor is too large to sample within max_points.")


def _floor_hour(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


class CorridorForecaster:
    def __init__(
        self,
        weather: WeatherProvider,
        *,
        spacing_miles: float = DEFAULT_SPACING_MILES,
        buffer_miles: float = DEFAULT_BUFFER_MILES,
        max_points: int = DEFAULT_MAX_POINTS,
    ) -> None:
        self._weather = weather
        self._spacing = spacing_miles
        self._buffer = buffer_miles
        self._max_points = max_points

    def forecast(
        self,
        routes: Sequence[Sequence[Coordinate]],
        departure_at: datetime,
        load_weight_lb: float,
    ) -> CorridorForecast:
        """Risk at every grid point for each whole hour from departure to departure + 48 h."""
        if departure_at.tzinfo is None:
            raise ValueError("Departure time must be timezone-aware.")
        grid = build_corridor_grid(
            routes,
            spacing_miles=self._spacing,
            buffer_miles=self._buffer,
            max_points=self._max_points,
        )
        start = _floor_hour(departure_at)
        hours = [start + timedelta(hours=h) for h in range(FORECAST_HOURS + 1)]
        forecasts = self._weather.hourly_forecasts(grid.points, hours[0], hours[-1])

        risk: list[list[RiskLevel | None]] = []
        for hour in hours:
            row: list[RiskLevel | None] = []
            for forecast in forecasts:
                conditions = conditions_at(forecast, hour)
                level = None
                if conditions is not None:
                    try:
                        level = assess_conditions(conditions, load_weight_lb).level
                    except InvalidWeatherError:
                        logger.warning("Invalid corridor weather at %s", hour.isoformat())
                row.append(level)
            risk.append(row)
        return CorridorForecast(grid=grid, start_at=start, risk=risk)
