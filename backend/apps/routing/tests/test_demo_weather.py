from datetime import UTC, datetime, timedelta

import pytest

from apps.routing.domain.risk_levels import RiskLevel
from apps.routing.services.corridor_forecast import CorridorForecaster
from apps.routing.services.demo_weather import NO_DATA_FROM_HOUR, DemoWeatherProvider
from apps.routing.services.geo import EARTH_RADIUS_MILES

from .fakes import NORTH, SOUTH, STRAIGHT, make_planner
from .test_trip_planner import trip

# A 300-mile trip due east along latitude 0, so miles map simply onto degrees.
MPD = EARTH_RADIUS_MILES * 3.141592653589793 / 180
ORIGIN, DESTINATION = (0.0, 0.0), (300 / MPD, 0.0)
START = datetime(2026, 11, 13, 13, 0, tzinfo=UTC)


def at(along_miles: float, left_miles: float) -> tuple[float, float]:
    return (along_miles / MPD, left_miles / MPD)


@pytest.fixture
def demo() -> DemoWeatherProvider:
    return DemoWeatherProvider(ORIGIN, DESTINATION, START + timedelta(minutes=20))


def test_wind_cell_sits_left_of_the_trip(demo: DemoWeatherProvider) -> None:
    # Hour 0: centre at 35% along (105 mi), 12% of trip to the left (36 mi).
    wind, rain, snow = demo.conditions(at(105, 36), START)
    assert wind == 58.0 and rain == 0.0 and snow == 0.0
    assert demo.conditions(at(105, -36), START)[0] == 8.0  # right side stays calm


def test_rain_band_crosses_the_trip_and_drifts(demo: DemoWeatherProvider) -> None:
    assert demo.conditions(at(195, 0), START)[1] == 0.6
    # Ten hours later the band has moved 10% of the trip (30 mi) forward.
    assert demo.conditions(at(225, 0), START + timedelta(hours=10))[1] == 0.6
    assert demo.conditions(at(195, 0), START + timedelta(hours=19))[1] == 0.0  # band over


def test_snow_forms_later_on_the_right(demo: DemoWeatherProvider) -> None:
    snow_spot = at(75, -45)
    assert demo.conditions(snow_spot, START + timedelta(hours=10))[2] == 0.0
    assert demo.conditions(snow_spot, START + timedelta(hours=20))[2] == 2.4


def test_data_ends_at_the_demo_horizon(demo: DemoWeatherProvider) -> None:
    assert demo.conditions(at(10, 0), START + timedelta(hours=NO_DATA_FROM_HOUR - 1)) is not None
    assert demo.conditions(at(10, 0), START + timedelta(hours=NO_DATA_FROM_HOUR)) is None


def test_corridor_shows_every_state_across_the_slider() -> None:
    routes = [STRAIGHT.coordinates, NORTH.coordinates, SOUTH.coordinates]
    provider = DemoWeatherProvider(routes[0][0], routes[0][-1], START)

    forecast = CorridorForecaster(provider, spacing_miles=8).forecast(routes, START, 35_000)
    seen = {level for hour in forecast.risk for level in hour}

    assert {RiskLevel.LOW, RiskLevel.HIGH, RiskLevel.SEVERE, RiskLevel.NO_TRAVEL, None} <= seen


def test_demo_trip_is_labelled_and_uses_the_real_risk_engine() -> None:
    analysis = make_planner(demo=True).analyze_trip(trip())

    assert analysis.weather_source == "demo"
    assert analysis.warnings[0].code == "DEMO_WEATHER"
    levels = {cp.assessment.level for r in analysis.routes for cp in r.checkpoints if cp.assessment}
    assert levels - {RiskLevel.LOW}  # storms reach at least one route


def test_live_trip_is_labelled_live() -> None:
    assert make_planner().analyze_trip(trip()).weather_source == "live"
