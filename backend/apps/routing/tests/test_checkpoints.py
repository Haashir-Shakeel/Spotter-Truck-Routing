from datetime import UTC, datetime, timedelta
from itertools import pairwise
from zoneinfo import ZoneInfo

import pytest

from apps.routing.domain.types import Checkpoint
from apps.routing.services.checkpoints import checkpoint_distances, generate_checkpoints
from apps.routing.services.geo import EARTH_RADIUS_MILES, haversine_miles

# Miles per degree of longitude on the equator (and of latitude anywhere) for our sphere.
MILES_PER_DEGREE = EARTH_RADIUS_MILES * 3.141592653589793 / 180
DEPARTURE = datetime(2026, 11, 13, 8, 0, tzinfo=ZoneInfo("America/Chicago"))


def deg(miles: float) -> float:
    return miles / MILES_PER_DEGREE


def equator_route(miles: float, vertices: int = 50) -> list[tuple[float, float]]:
    return [(deg(miles) * i / (vertices - 1), 0.0) for i in range(vertices)]


def distances(checkpoints: list[Checkpoint]) -> list[float]:
    return [cp.distance_miles for cp in checkpoints]


# --- geo -------------------------------------------------------------------------------------


def test_haversine_chicago_to_detroit() -> None:
    chicago, detroit = (-87.6298, 41.8781), (-83.0458, 42.3314)
    assert haversine_miles(chicago, detroit) == pytest.approx(237.5, rel=0.01)


# --- spacing ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("total", "interval", "expected"),
    [
        (112, 25, [0, 25, 50, 75, 100, 112]),
        (100, 25, [0, 25, 50, 75, 100]),  # divisible: destination not duplicated
        (8, 10, [0, 8]),  # shorter than one interval
        (120, 50, [0, 50, 100, 120]),
        (30, 10, [0, 10, 20, 30]),
    ],
)
def test_checkpoint_distances(total: float, interval: int, expected: list[float]) -> None:
    assert checkpoint_distances(total, interval) == pytest.approx(expected)


def test_float_noise_does_not_add_a_near_duplicate_destination() -> None:
    positions = checkpoint_distances(0.1 * 3 * 1000, 10)  # 300.00000000000006
    assert len(positions) == 31
    assert positions[-1] == pytest.approx(300)


def test_112_mile_route_at_25_miles() -> None:
    checkpoints = generate_checkpoints(
        coordinates=equator_route(112),
        interval_miles=25,
        departure_at=DEPARTURE,
        total_duration_seconds=7200,
    )

    assert distances(checkpoints) == pytest.approx([0, 25, 50, 75, 100, 112])
    assert [cp.index for cp in checkpoints] == list(range(6))
    assert checkpoints[2].lon == pytest.approx(deg(50))


@pytest.mark.parametrize("interval", [10, 25, 50])
def test_every_interval_includes_origin_and_destination(interval: int) -> None:
    coords = equator_route(137)
    checkpoints = generate_checkpoints(
        coordinates=coords,
        interval_miles=interval,
        departure_at=DEPARTURE,
        total_duration_seconds=9000,
    )

    assert (checkpoints[0].lon, checkpoints[0].lat) == pytest.approx(coords[0])
    assert (checkpoints[-1].lon, checkpoints[-1].lat) == pytest.approx(coords[-1])
    gaps = [b.distance_miles - a.distance_miles for a, b in pairwise(checkpoints)]
    assert all(gap == pytest.approx(interval) for gap in gaps[:-1])
    assert 0 < gaps[-1] <= interval + 1e-9


def test_checkpoints_follow_the_road_around_a_turn() -> None:
    # 50 miles east, then 50 miles north. Mile 75 must be on the northbound leg.
    corner = (deg(50), 0.0)
    coords = [(0.0, 0.0), corner, (deg(50), deg(50))]

    checkpoints = generate_checkpoints(
        coordinates=coords,
        interval_miles=25,
        departure_at=DEPARTURE,
        total_duration_seconds=6000,
    )

    at_75 = checkpoints[3]
    assert at_75.distance_miles == pytest.approx(75, rel=1e-3)
    assert at_75.lon == pytest.approx(corner[0], abs=1e-9)
    assert at_75.lat == pytest.approx(deg(25), rel=1e-3)
    assert checkpoints[-1].distance_miles == pytest.approx(100, rel=1e-3)


def test_distances_are_scaled_to_provider_road_distance() -> None:
    checkpoints = generate_checkpoints(
        coordinates=equator_route(100),
        interval_miles=25,
        departure_at=DEPARTURE,
        total_duration_seconds=7200,
        total_distance_miles=110,
    )

    assert distances(checkpoints) == pytest.approx([0, 25, 50, 75, 100, 110])
    # 100 road miles of 110 is 10/11 of the way along the geometry.
    assert checkpoints[4].lon == pytest.approx(deg(100) * 100 / 110)


def test_duplicate_vertices_are_handled() -> None:
    coords = [(0.0, 0.0), (deg(10), 0.0), (deg(10), 0.0), (deg(30), 0.0)]
    checkpoints = generate_checkpoints(
        coordinates=coords, interval_miles=10, departure_at=DEPARTURE, total_duration_seconds=1800
    )

    assert distances(checkpoints) == pytest.approx([0, 10, 20, 30])


# --- ETA -------------------------------------------------------------------------------------


def test_proportional_eta_when_no_segment_timings() -> None:
    checkpoints = generate_checkpoints(
        coordinates=equator_route(100),
        interval_miles=50,
        departure_at=DEPARTURE,
        total_duration_seconds=7200,
    )

    assert [cp.elapsed_seconds for cp in checkpoints] == pytest.approx([0, 3600, 7200])
    assert checkpoints[1].arrival_at == datetime(2026, 11, 13, 15, 0, tzinfo=UTC)


def test_eta_uses_segment_durations_when_available() -> None:
    # First 50 miles take 1 h (highway), next 50 miles take 3 h (slow).
    coords = [(0.0, 0.0), (deg(50), 0.0), (deg(100), 0.0)]
    checkpoints = generate_checkpoints(
        coordinates=coords,
        interval_miles=25,
        departure_at=DEPARTURE,
        total_duration_seconds=4 * 3600,
        cumulative_durations=[0, 3600, 4 * 3600],
    )

    elapsed_hours = [cp.elapsed_seconds / 3600 for cp in checkpoints]
    assert elapsed_hours == pytest.approx([0, 0.5, 1, 2.5, 4], rel=1e-3)


def test_etas_increase_monotonically() -> None:
    coords = equator_route(260, vertices=200)
    durations = [i * i for i in range(200)]  # uneven speeds
    checkpoints = generate_checkpoints(
        coordinates=coords,
        interval_miles=10,
        departure_at=DEPARTURE,
        total_duration_seconds=durations[-1],
        cumulative_durations=durations,
    )

    arrivals = [cp.arrival_at for cp in checkpoints]
    assert arrivals == sorted(arrivals)
    assert len(set(arrivals)) == len(arrivals)


def test_arrival_times_are_utc_across_midnight_and_dst() -> None:
    # 2026-11-01 02:00 is the US fall-back. Depart 23:30 local the night before.
    departure = datetime(2026, 10, 31, 23, 30, tzinfo=ZoneInfo("America/Chicago"))
    checkpoints = generate_checkpoints(
        coordinates=equator_route(100),
        interval_miles=50,
        departure_at=departure,
        total_duration_seconds=4 * 3600,
    )

    assert departure.utcoffset() == timedelta(hours=-5)  # still CDT
    assert checkpoints[0].arrival_at == datetime(2026, 11, 1, 4, 30, tzinfo=UTC)
    assert checkpoints[-1].arrival_at == datetime(2026, 11, 1, 8, 30, tzinfo=UTC)
    assert all(cp.arrival_at.tzinfo is UTC for cp in checkpoints)
    # Locally the truck arrives at 02:30 CST, after clocks went back.
    assert checkpoints[-1].arrival_at.astimezone(departure.tzinfo).hour == 2


# --- validation ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"interval_miles": 15},
        {"departure_at": datetime(2026, 11, 13, 8, 0)},  # naive on purpose
        {"total_duration_seconds": 0},
        {"coordinates": [(0.0, 0.0)]},
        {"coordinates": [(0.0, 0.0), (0.0, 0.0)]},  # zero length
        {"coordinates": [(0.0, 0.0), (200.0, 0.0)]},  # out of range
        {"total_distance_miles": -5},
        {"cumulative_durations": [0, 10]},  # wrong length
        {"cumulative_durations": [0, 3600, 1800]},  # decreasing
    ],
    ids=[
        "bad-interval",
        "naive-departure",
        "zero-duration",
        "one-coordinate",
        "zero-length",
        "out-of-range",
        "negative-distance",
        "durations-length",
        "durations-decreasing",
    ],
)
def test_invalid_input_rejected(overrides: dict) -> None:
    kwargs = {
        "coordinates": equator_route(50, vertices=3),
        "interval_miles": 10,
        "departure_at": DEPARTURE,
        "total_duration_seconds": 3600,
        **overrides,
    }
    with pytest.raises(ValueError):
        generate_checkpoints(**kwargs)
