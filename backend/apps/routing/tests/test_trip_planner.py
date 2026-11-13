from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from apps.routing.domain.risk_levels import RiskLevel
from apps.routing.domain.types import RecommendationStatus
from apps.routing.services.errors import NoRouteFoundError, ProviderUnavailableError, TripInputError
from apps.routing.services.trip_planner import LocationInput, TripRequest

from .fakes import (
    DESTINATION,
    NORTH,
    NOW,
    ORIGIN,
    SOUTH,
    STRAIGHT,
    FakeGeocoder,
    FakeRouter,
    FakeWeather,
    make_planner,
    make_route,
)

DEPARTURE = NOW + timedelta(hours=1)


def trip(**overrides) -> TripRequest:
    values = {
        "origin": LocationInput("Origin"),
        "destination": LocationInput("Destination"),
        "departure_at": DEPARTURE,
        "load_weight_lb": 20_000,
        "checkpoint_interval_miles": 25,
        **overrides,
    }
    return TripRequest(**values)


def test_calm_weather_recommends_the_fastest_of_three_routes() -> None:
    analysis = make_planner().analyze_trip(trip())

    assert [r.route.route_id for r in analysis.routes] == ["A", "B", "C"]
    assert [r.label for r in analysis.routes] == ["Route A", "Route B", "Route C"]
    assert analysis.recommendation.status is RecommendationStatus.ROUTE_AVAILABLE
    assert analysis.recommendation.recommended_route_id == "A"  # straight route is shortest
    assert analysis.warnings == []
    for route in analysis.routes:
        assert route.summary.max_risk is RiskLevel.LOW
        assert route.summary.is_complete
        assert route.eta_method == "segment_durations"
        assert route.checkpoints[0].checkpoint.distance_miles == 0
        assert route.checkpoints[-1].checkpoint.distance_miles == pytest.approx(
            route.route.distance_miles
        )


def test_severe_snow_on_the_fastest_route_moves_the_recommendation() -> None:
    def snow_on_straight_road(lon: float, lat: float, when: datetime):
        on_straight = abs(lat - 40.0) < 0.01 and -89.6 < lon < -88.4
        return (5.0, 0.0, 2.5 if on_straight else 0.0)

    analysis = make_planner(weather=FakeWeather(snow_on_straight_road)).analyze_trip(trip())

    route_a = analysis.routes[0]
    assert route_a.summary.severe_miles > 0
    assert analysis.recommendation.recommended_route_id == "B"
    assert "Severe miles" in analysis.recommendation.explanation


def test_weather_is_taken_at_each_checkpoints_arrival_time() -> None:
    # Calm at departure hour, 60 mph winds from one hour later. The ~1 h 46 min trip means the
    # first checkpoint meets calm air and the destination meets the storm, at the same place.
    storm_from = DEPARTURE + timedelta(hours=1)

    def storm_later(lon: float, lat: float, when: datetime):
        return (60.0, 0.0, 0.0) if when >= storm_from else (5.0, 0.0, 0.0)

    analysis = make_planner(weather=FakeWeather(storm_later)).analyze_trip(trip())

    checkpoints = analysis.routes[0].checkpoints
    assert checkpoints[0].checkpoint.arrival_at == DEPARTURE
    assert checkpoints[0].assessment.level is RiskLevel.LOW
    assert checkpoints[-1].checkpoint.arrival_at > storm_from
    assert checkpoints[-1].assessment.level is RiskLevel.NO_TRAVEL


def test_load_weight_override_is_applied() -> None:
    windy = FakeWeather(lambda lon, lat, when: (40.0, 0.0, 0.0))

    light = make_planner(weather=windy).analyze_trip(trip(load_weight_lb=20_000))
    heavy = make_planner(weather=windy).analyze_trip(trip(load_weight_lb=45_000))

    assert light.routes[0].summary.max_risk is RiskLevel.HIGH
    assert heavy.routes[0].summary.max_risk is RiskLevel.SEVERE
    assert heavy.routes[0].checkpoints[0].assessment.load_override is not None


def test_no_travel_everywhere_means_no_safe_route() -> None:
    gale = FakeWeather(lambda lon, lat, when: (60.0, 0.0, 0.0))

    analysis = make_planner(weather=gale).analyze_trip(trip())

    assert analysis.recommendation.status is RecommendationStatus.NO_SAFE_ROUTE
    assert analysis.recommendation.recommended_route_id is None


def test_missing_forecast_is_unavailable_and_warned() -> None:
    def gap_on_north(lon: float, lat: float, when: datetime):
        return None if lat > 40.2 else (5.0, 0.0, 0.0)

    analysis = make_planner(weather=FakeWeather(gap_on_north)).analyze_trip(trip())

    route_b = analysis.routes[1]
    assert route_b.summary.unavailable_miles > 0
    assert any(cp.assessment is None and cp.weather is None for cp in route_b.checkpoints)
    assert "B" in analysis.recommendation.ineligible
    assert [w.code for w in analysis.warnings] == ["WEATHER_UNAVAILABLE"]


def test_fewer_routes_are_reported_not_padded() -> None:
    analysis = make_planner(router=FakeRouter([STRAIGHT, NORTH])).analyze_trip(trip())

    assert len(analysis.routes) == 2
    assert [w.code for w in analysis.warnings] == ["FEWER_ROUTES"]
    assert "2 distinct routes" in analysis.warnings[0].message


def test_detour_route_fills_in_when_provider_offers_two() -> None:
    detour = make_route("detour", [(-89.0, 39.7)])  # ~7% longer, same speed
    router = FakeRouter([STRAIGHT, NORTH], detours=[detour])
    analysis = make_planner(router=router).analyze_trip(trip())

    assert [r.route.route_id for r in analysis.routes] == ["A", "B", "C"]
    assert analysis.routes[2].route.via is not None
    assert analysis.routes[0].route.via is None
    assert [w.code for w in analysis.warnings] == ["VIA_ROUTE"]
    assert "offered 2 routes" in analysis.warnings[0].message
    assert "Route C is a real drivable route" in analysis.warnings[0].message


def test_detour_waypoints_sit_either_side_of_the_trip_midpoint() -> None:
    router = FakeRouter([STRAIGHT, NORTH])  # no detour succeeds
    make_planner(router=router).analyze_trip(trip())

    # Origin (-90, 40) -> destination (-88, 40): travel east, so left is north.
    left, right, far_left, far_right = router.via_calls
    assert left[0] == pytest.approx(-89.0) and left[1] > 40
    assert right[1] < 40
    assert far_left[1] > left[1] and far_right[1] < right[1]


def test_detour_that_duplicates_or_is_too_slow_is_rejected() -> None:
    slow = make_route("slow", [(-89.0, 41.5)], mph=30)  # far more than 30% slower
    router = FakeRouter([STRAIGHT, NORTH], detours=[NORTH, slow])
    analysis = make_planner(router=router).analyze_trip(trip())

    assert len(analysis.routes) == 2
    assert [w.code for w in analysis.warnings] == ["FEWER_ROUTES"]


def test_failed_detour_request_does_not_fail_the_analysis() -> None:
    class FlakyDetours(FakeRouter):
        def get_routes(self, origin, destination, *, via=None):
            if via is not None:
                raise ProviderUnavailableError("Mapbox Directions", "timed out")
            return super().get_routes(origin, destination)

    analysis = make_planner(router=FlakyDetours([STRAIGHT])).analyze_trip(trip())

    assert len(analysis.routes) == 1


def test_duplicate_provider_routes_count_once() -> None:
    copy = replace(STRAIGHT, route_id="p9")
    analysis = make_planner(router=FakeRouter([STRAIGHT, copy, SOUTH])).analyze_trip(trip())

    assert [r.route.route_id for r in analysis.routes] == ["A", "B"]
    assert analysis.warnings[0].code == "FEWER_ROUTES"


def test_no_route_raises() -> None:
    with pytest.raises(NoRouteFoundError):
        make_planner(router=FakeRouter([])).analyze_trip(trip())


def test_weather_is_fetched_once_for_all_routes_with_shared_points_deduplicated() -> None:
    weather = FakeWeather()
    analysis = make_planner(weather=weather).analyze_trip(trip())

    assert len(weather.calls) == 1
    points, start, end = weather.calls[0]
    assert len(points) == len(set(points))
    total_checkpoints = sum(len(r.checkpoints) for r in analysis.routes)
    assert len(points) < total_checkpoints  # shared origin/destination fetched once
    arrivals = [cp.checkpoint.arrival_at for r in analysis.routes for cp in r.checkpoints]
    assert start <= min(arrivals) and end >= max(arrivals)


def test_selected_suggestion_coordinates_skip_geocoding() -> None:
    geocoder = FakeGeocoder(places={})
    analysis = make_planner(geocoder=geocoder).analyze_trip(
        trip(
            origin=LocationInput("Picked origin", lon=ORIGIN.lon, lat=ORIGIN.lat),
            destination=LocationInput(
                "Picked destination", lon=DESTINATION.lon, lat=DESTINATION.lat
            ),
        )
    )

    assert geocoder.queries == []
    assert analysis.origin.name == "Picked origin"


def test_unknown_place_is_an_input_error() -> None:
    with pytest.raises(TripInputError) as excinfo:
        make_planner().analyze_trip(trip(destination=LocationInput("Atlantis")))

    assert excinfo.value.code == "LOCATION_NOT_FOUND"
    assert excinfo.value.details == {"field": "destination"}


def test_same_origin_and_destination_rejected() -> None:
    with pytest.raises(TripInputError) as excinfo:
        make_planner().analyze_trip(trip(destination=LocationInput("Origin")))
    assert excinfo.value.code == "SAME_LOCATION"


@pytest.mark.parametrize(
    ("departure", "code"),
    [
        (NOW - timedelta(hours=2), "DEPARTURE_IN_PAST"),
        (NOW + timedelta(days=15), "DEPARTURE_TOO_FAR"),
        (datetime(2026, 11, 13, 13, 0), "INVALID_DEPARTURE"),
    ],
    ids=["past", "too-far", "naive"],
)
def test_departure_outside_forecast_window_rejected(departure: datetime, code: str) -> None:
    router = FakeRouter()
    with pytest.raises(TripInputError) as excinfo:
        make_planner(router=router).analyze_trip(trip(departure_at=departure))

    assert excinfo.value.code == code
    assert router.calls == []  # rejected before any provider call
