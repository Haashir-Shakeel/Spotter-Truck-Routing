"""Small geodesic helpers for route polylines (spherical Earth, accurate to well under 1%)."""

import math
from collections.abc import Sequence
from itertools import accumulate, pairwise

from apps.routing.domain.types import Coordinate

EARTH_RADIUS_MILES = 3958.7613


def haversine_miles(a: Coordinate, b: Coordinate) -> float:
    """Great-circle distance between two (lon, lat) points in miles."""
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * math.asin(min(1.0, math.sqrt(h)))


def cumulative_distances_miles(coordinates: Sequence[Coordinate]) -> list[float]:
    """Distance from the first vertex to every vertex, following the polyline."""
    segment_lengths = (haversine_miles(a, b) for a, b in pairwise(coordinates))
    return list(accumulate(segment_lengths, initial=0.0))


def validate_coordinates(coordinates: Sequence[Coordinate]) -> None:
    if len(coordinates) < 2:
        raise ValueError("A route geometry needs at least two coordinates.")
    for lon, lat in coordinates:
        if not (math.isfinite(lon) and math.isfinite(lat)):
            raise ValueError(f"Coordinate must be finite, got ({lon}, {lat}).")
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError(f"Coordinate out of range (lon, lat): ({lon}, {lat}).")
