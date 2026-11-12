"""Place weather checkpoints along the road and estimate when the truck reaches each one.

Checkpoints sit every N road miles (0, N, 2N, ... and always the destination), measured along the
route polyline, never on a straight line between origin and destination.

Arrival time:
- If the provider gives per-vertex cumulative durations, elapsed time is interpolated within the
  road segment that contains the checkpoint (handles slow city and fast highway stretches).
- Otherwise elapsed time is proportional to distance:
  ``total_duration * checkpoint_miles / total_miles``. This is an approximation.

All timestamps are UTC. Departure must be timezone-aware so DST and offsets are unambiguous.
"""

import math
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from itertools import pairwise

from apps.routing.domain.types import Checkpoint, Coordinate

from .geo import (
    cumulative_distances_miles,
    interpolate_on_segment,
    segment_position,
    validate_coordinates,
)

ALLOWED_INTERVALS_MILES = (10, 25, 50)

# A destination closer than this to the last interval multiple is treated as the same point.
_SAME_POINT_MILES = 1e-6


def checkpoint_distances(total_miles: float, interval_miles: float) -> list[float]:
    """Road-mile positions: 0, S, 2S, ..., and the destination (without duplicating it)."""
    if total_miles <= 0:
        raise ValueError("Route distance must be positive.")
    if interval_miles <= 0:
        raise ValueError("Checkpoint interval must be positive.")

    count = math.floor(total_miles / interval_miles + _SAME_POINT_MILES)
    positions = [i * interval_miles for i in range(count + 1)]
    if total_miles - positions[-1] > _SAME_POINT_MILES:
        positions.append(total_miles)
    else:
        positions[-1] = total_miles
    return positions


def _validate_durations(cumulative_durations: Sequence[float], vertex_count: int) -> None:
    if len(cumulative_durations) != vertex_count:
        raise ValueError("cumulative_durations must have one value per coordinate.")
    if cumulative_durations[0] != 0:
        raise ValueError("cumulative_durations must start at 0.")
    if any(b < a for a, b in pairwise(cumulative_durations)):
        raise ValueError("cumulative_durations must not decrease.")


def generate_checkpoints(
    *,
    coordinates: Sequence[Coordinate],
    interval_miles: int,
    departure_at: datetime,
    total_duration_seconds: float,
    total_distance_miles: float | None = None,
    cumulative_durations: Sequence[float] | None = None,
) -> list[Checkpoint]:
    """Build checkpoints along ``coordinates``.

    ``total_distance_miles`` is the provider's road distance. When given, polyline distances are
    scaled to match it, so checkpoint mileage agrees with the distance shown to the driver.
    """
    if interval_miles not in ALLOWED_INTERVALS_MILES:
        raise ValueError(f"interval_miles must be one of {ALLOWED_INTERVALS_MILES}.")
    if departure_at.tzinfo is None or departure_at.utcoffset() is None:
        raise ValueError("departure_at must be timezone-aware.")
    if not math.isfinite(total_duration_seconds) or total_duration_seconds <= 0:
        raise ValueError("total_duration_seconds must be positive.")
    validate_coordinates(coordinates)

    cumulative = cumulative_distances_miles(coordinates)
    geometry_miles = cumulative[-1]
    if geometry_miles <= 0:
        raise ValueError("Route geometry has zero length.")

    if total_distance_miles is not None:
        if not math.isfinite(total_distance_miles) or total_distance_miles <= 0:
            raise ValueError("total_distance_miles must be positive.")
        scale = total_distance_miles / geometry_miles
        cumulative = [d * scale for d in cumulative]
    route_miles = cumulative[-1]

    if cumulative_durations is not None:
        _validate_durations(cumulative_durations, len(coordinates))

    departure_utc = departure_at.astimezone(UTC)
    checkpoints: list[Checkpoint] = []

    for index, distance in enumerate(checkpoint_distances(route_miles, interval_miles)):
        seg, fraction = segment_position(cumulative, distance)
        lon, lat = interpolate_on_segment(coordinates, seg, fraction)

        if cumulative_durations is not None:
            start, end = cumulative_durations[seg], cumulative_durations[seg + 1]
            elapsed = start + fraction * (end - start)
        else:
            elapsed = total_duration_seconds * distance / route_miles

        checkpoints.append(
            Checkpoint(
                index=index,
                lon=lon,
                lat=lat,
                distance_miles=distance,
                elapsed_seconds=elapsed,
                arrival_at=departure_utc + timedelta(seconds=elapsed),
            )
        )

    return checkpoints
