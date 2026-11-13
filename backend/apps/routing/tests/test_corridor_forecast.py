from datetime import UTC, datetime, timedelta
from itertools import pairwise

import pytest

from apps.routing.domain.risk_levels import RiskLevel
from apps.routing.services.corridor_forecast import (
    FORECAST_HOURS,
    CorridorForecaster,
    build_corridor_grid,
)
from apps.routing.services.geo import haversine_miles

from .fakes import NORTH, SOUTH, STRAIGHT, FakeWeather

ROUTES = [STRAIGHT.coordinates, NORTH.coordinates, SOUTH.coordinates]
DEPARTURE = datetime(2026, 11, 13, 13, 40, tzinfo=UTC)


def distance_to_routes(point: tuple[float, float]) -> float:
    """Nearest distance to any route vertex or densified point (good to ~1 mile)."""
    samples = []
    for route in ROUTES:
        for (lon1, lat1), (lon2, lat2) in pairwise(route):
            samples += [
                (lon1 + (lon2 - lon1) * i / 100, lat1 + (lat2 - lat1) * i / 100) for i in range(101)
            ]
    return min(haversine_miles(point, s) for s in samples)


# --- grid -------------------------------------------------------------------------------------


def test_grid_points_stay_within_the_buffer_of_some_route() -> None:
    grid = build_corridor_grid(ROUTES, spacing_miles=10, buffer_miles=15)

    assert len(grid.points) > 20
    assert all(distance_to_routes(p) <= 15 + 0.5 for p in grid.points)


def test_grid_covers_the_corridor_without_gaps() -> None:
    grid = build_corridor_grid(ROUTES, spacing_miles=10, buffer_miles=15)

    # Every route vertex has a grid point within one spacing.
    for route in ROUTES:
        for vertex in route:
            assert min(haversine_miles(vertex, p) for p in grid.points) <= 10


def test_grid_is_evenly_spaced_on_the_ground() -> None:
    grid = build_corridor_grid(ROUTES, spacing_miles=10, buffer_miles=15)

    nearest = [min(haversine_miles(p, q) for q in grid.points if q is not p) for p in grid.points]
    # Triangular lattice: nearest neighbours sit ~spacing apart in miles, not in degrees.
    assert min(nearest) > 8.5
    assert max(nearest) < 11.5
    assert len(set(grid.points)) == len(grid.points)


def test_grid_widens_spacing_to_respect_max_points() -> None:
    grid = build_corridor_grid(ROUTES, spacing_miles=5, buffer_miles=20, max_points=40)

    assert len(grid.points) <= 40
    assert grid.spacing_miles > 5


def test_grid_is_deterministic() -> None:
    assert build_corridor_grid(ROUTES) == build_corridor_grid(ROUTES)


def test_grid_rejects_degenerate_routes() -> None:
    with pytest.raises(ValueError):
        build_corridor_grid([[(-90.0, 40.0)]])
    with pytest.raises(ValueError):
        build_corridor_grid([])


# --- forecast ---------------------------------------------------------------------------------


def test_forecast_has_49_hourly_slices_from_departure_hour() -> None:
    weather = FakeWeather()
    forecast = CorridorForecaster(weather, spacing_miles=20).forecast(ROUTES, DEPARTURE, 20_000)

    assert forecast.hour_count == FORECAST_HOURS + 1 == 49
    assert forecast.start_at == datetime(2026, 11, 13, 13, 0, tzinfo=UTC)
    assert all(len(hour) == len(forecast.grid.points) for hour in forecast.risk)
    assert all(level == RiskLevel.LOW for hour in forecast.risk for level in hour)
    # One batched provider call covering exactly hours 0..48.
    ((points, start, end),) = weather.calls
    assert points == forecast.grid.points
    assert (start, end) == (forecast.start_at, forecast.start_at + timedelta(hours=48))


def test_forecast_tracks_weather_changing_over_time() -> None:
    storm_at = DEPARTURE.replace(minute=0) + timedelta(hours=24)

    def storm_at_hour_24(lon: float, lat: float, when: datetime) -> tuple[float, float, float]:
        return (40.0, 0.0, 0.0) if when == storm_at else (5.0, 0.0, 0.0)

    forecast = CorridorForecaster(FakeWeather(storm_at_hour_24), spacing_miles=20).forecast(
        ROUTES, DEPARTURE, 45_000
    )

    assert set(forecast.risk[0]) == {RiskLevel.LOW}
    # 40 mph is High; a 45,000 lb load raises it to Severe, same rules as the routes.
    assert set(forecast.risk[24]) == {RiskLevel.SEVERE}
    assert set(forecast.risk[48]) == {RiskLevel.LOW}


def test_missing_forecast_stays_unavailable_not_low() -> None:
    cutoff = DEPARTURE + timedelta(hours=30)

    def ends_at_hour_30(
        lon: float, lat: float, when: datetime
    ) -> tuple[float, float, float] | None:
        return (5.0, 0.0, 0.0) if when <= cutoff else None

    forecast = CorridorForecaster(FakeWeather(ends_at_hour_30), spacing_miles=20).forecast(
        ROUTES, DEPARTURE, 20_000
    )

    assert set(forecast.risk[30]) == {RiskLevel.LOW}
    assert set(forecast.risk[31]) == {None}
    assert set(forecast.risk[48]) == {None}


def test_forecast_requires_aware_departure() -> None:
    with pytest.raises(ValueError):
        CorridorForecaster(FakeWeather()).forecast(ROUTES, DEPARTURE.replace(tzinfo=None), 1)
