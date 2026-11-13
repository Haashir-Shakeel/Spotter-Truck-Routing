"""Small geodesic helpers for route polylines (spherical Earth, accurate to well under 1%)."""

import math
from bisect import bisect_right
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


def segment_position(cumulative: Sequence[float], target: float) -> tuple[int, float]:
    """Segment index containing ``target`` miles, and the fraction (0..1) along it."""
    last_segment = len(cumulative) - 2
    i = min(max(bisect_right(cumulative, target) - 1, 0), last_segment)
    length = cumulative[i + 1] - cumulative[i]
    fraction = 0.0 if length <= 0 else (target - cumulative[i]) / length
    return i, min(max(fraction, 0.0), 1.0)


def interpolate_on_segment(
    coordinates: Sequence[Coordinate], segment: int, fraction: float
) -> Coordinate:
    """Linear interpolation inside one polyline segment (road segments are short)."""
    (lon1, lat1), (lon2, lat2) = coordinates[segment], coordinates[segment + 1]
    return lon1 + fraction * (lon2 - lon1), lat1 + fraction * (lat2 - lat1)


def point_at_distance(
    coordinates: Sequence[Coordinate], cumulative: Sequence[float], target: float
) -> Coordinate:
    return interpolate_on_segment(coordinates, *segment_position(cumulative, target))


def offset_midpoint(a: Coordinate, b: Coordinate, offset_miles: float) -> Coordinate:
    """Point beside the middle of segment a->b, ``offset_miles`` to the left (negative: right).

    Uses a local equirectangular projection, accurate enough for picking a detour waypoint.
    """
    mid_lon, mid_lat = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    miles_per_deg_lat = EARTH_RADIUS_MILES * math.radians(1)
    miles_per_deg_lon = miles_per_deg_lat * math.cos(math.radians(mid_lat))
    dx = (b[0] - a[0]) * miles_per_deg_lon
    dy = (b[1] - a[1]) * miles_per_deg_lat
    length = math.hypot(dx, dy)
    if length == 0:
        return mid_lon, mid_lat
    # Left normal of the travel direction.
    nx, ny = -dy / length, dx / length
    return (
        mid_lon + nx * offset_miles / miles_per_deg_lon,
        mid_lat + ny * offset_miles / miles_per_deg_lat,
    )


def simplify_polyline(
    coordinates: Sequence[Coordinate], tolerance_miles: float
) -> list[Coordinate]:
    """Douglas-Peucker simplification for display; always keeps both endpoints.

    Distances are measured in a local equirectangular projection (miles), which is accurate at
    the sub-mile scale of a tolerance. Checkpoints are computed from the full geometry, never
    from this simplified copy.
    """
    if len(coordinates) <= 2:
        return list(coordinates)
    mid_lat = math.radians(sum(lat for _, lat in coordinates) / len(coordinates))
    x_scale = EARTH_RADIUS_MILES * math.radians(1) * math.cos(mid_lat)
    y_scale = EARTH_RADIUS_MILES * math.radians(1)
    xy = [(lon * x_scale, lat * y_scale) for lon, lat in coordinates]

    keep = [False] * len(xy)
    keep[0] = keep[-1] = True
    stack = [(0, len(xy) - 1)]
    while stack:
        start, end = stack.pop()
        (x1, y1), (x2, y2) = xy[start], xy[end]
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        farthest, farthest_distance = -1, tolerance_miles
        for i in range(start + 1, end):
            px, py = xy[i]
            if length == 0:
                distance = math.hypot(px - x1, py - y1)
            else:
                distance = abs(dy * (px - x1) - dx * (py - y1)) / length
            if distance > farthest_distance:
                farthest, farthest_distance = i, distance
        if farthest >= 0:
            keep[farthest] = True
            stack.append((start, farthest))
            stack.append((farthest, end))
    return [c for c, kept in zip(coordinates, keep, strict=True) if kept]


def validate_coordinates(coordinates: Sequence[Coordinate]) -> None:
    if len(coordinates) < 2:
        raise ValueError("A route geometry needs at least two coordinates.")
    for lon, lat in coordinates:
        if not (math.isfinite(lon) and math.isfinite(lat)):
            raise ValueError(f"Coordinate must be finite, got ({lon}, {lat}).")
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError(f"Coordinate out of range (lon, lat): ({lon}, {lat}).")
