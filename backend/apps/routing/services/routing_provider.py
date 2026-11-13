"""Route alternatives from Mapbox Directions, normalized to ``RouteOption``.

Limitations (documented, not hidden):
- Mapbox returns *up to* three routes (the primary plus up to two alternatives). We never invent
  extra routes; callers must handle fewer.
- The public ``mapbox/driving`` profile is not truck-restricted (no height/weight limits).
- With a ``via`` waypoint, Mapbox returns one real route through that point (no alternatives).
  The planner uses this only when Mapbox offers fewer than three routes.
"""

from collections.abc import Sequence
from dataclasses import replace
from itertools import accumulate
from typing import Any, Protocol

import httpx

from apps.routing.domain.types import Coordinate, RouteOption

from .errors import ProviderConfigurationError, ProviderResponseError
from .geo import cumulative_distances_miles, haversine_miles, point_at_distance
from .http import get_json

METERS_PER_MILE = 1609.344
MAPBOX_DIRECTIONS_URL = "https://api.mapbox.com/directions/v5/mapbox/driving/{coordinates}"
_NO_ROUTE_CODES = frozenset({"NoRoute", "NoSegment"})
PROVIDER = "Mapbox Directions"


class RoutingProvider(Protocol):
    def get_routes(
        self, origin: Coordinate, destination: Coordinate, *, via: Coordinate | None = None
    ) -> list[RouteOption]: ...


class MapboxRoutingProvider:
    def __init__(self, client: httpx.Client, access_token: str, max_retries: int = 2) -> None:
        if not access_token:
            raise ProviderConfigurationError(PROVIDER, "MAPBOX_ACCESS_TOKEN is not set")
        self._client = client
        self._token = access_token
        self._max_retries = max_retries

    def get_routes(
        self, origin: Coordinate, destination: Coordinate, *, via: Coordinate | None = None
    ) -> list[RouteOption]:
        points = (origin, destination) if via is None else (origin, via, destination)
        path = ";".join(f"{lon:.6f},{lat:.6f}" for lon, lat in points)
        body = get_json(
            self._client,
            MAPBOX_DIRECTIONS_URL.format(coordinates=path),
            params={
                "alternatives": "false" if via else "true",
                "geometries": "geojson",
                "overview": "full",
                "annotations": "duration",
                "steps": "false",
                "access_token": self._token,
            },
            provider=PROVIDER,
            max_retries=self._max_retries,
        )
        routes = parse_mapbox_directions(body)
        return [replace(route, via=via) for route in routes] if via else routes


def _cumulative_durations(route: dict[str, Any], vertex_count: int) -> tuple[float, ...] | None:
    """Per-vertex elapsed seconds from leg annotations, or None if they don't line up."""
    segment_durations: list[float] = []
    for leg in route.get("legs", []):
        segment_durations.extend(leg.get("annotation", {}).get("duration", []))
    if len(segment_durations) != vertex_count - 1:
        return None
    return tuple(accumulate(segment_durations, initial=0.0))


def parse_mapbox_directions(body: Any) -> list[RouteOption]:
    if not isinstance(body, dict):
        raise ProviderResponseError(PROVIDER, "unexpected response shape")
    code = body.get("code")
    if code in _NO_ROUTE_CODES:
        return []
    if code != "Ok":
        raise ProviderResponseError(PROVIDER, f"returned code {code!r}")

    options: list[RouteOption] = []
    for index, route in enumerate(body.get("routes", []), start=1):
        try:
            coordinates = tuple(
                (float(lon), float(lat)) for lon, lat in route["geometry"]["coordinates"]
            )
            distance_m = float(route["distance"])
            duration_s = float(route["duration"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderResponseError(PROVIDER, f"route {index} is malformed") from exc
        if len(coordinates) < 2 or distance_m <= 0 or duration_s <= 0:
            continue
        options.append(
            RouteOption(
                route_id=f"route_{index}",
                coordinates=coordinates,
                distance_miles=distance_m / METERS_PER_MILE,
                duration_seconds=duration_s,
                cumulative_durations=_cumulative_durations(route, len(coordinates)),
            )
        )
    return options


def _sample_points(route: RouteOption, samples: int) -> list[Coordinate]:
    cumulative = cumulative_distances_miles(route.coordinates)
    total = cumulative[-1]
    return [
        point_at_distance(route.coordinates, cumulative, total * i / samples)
        for i in range(samples + 1)
    ]


def deduplicate_routes(
    routes: Sequence[RouteOption],
    *,
    tolerance_miles: float = 0.5,
    samples: int = 20,
) -> list[RouteOption]:
    """Drop routes that follow essentially the same roads as an earlier route.

    Compared by geometry (points at equal fractions along each route), not provider id, so two
    ids for the same road path are treated as one route.
    """
    kept: list[tuple[RouteOption, list[Coordinate]]] = []
    for route in routes:
        points = _sample_points(route, samples)
        is_duplicate = any(
            all(
                haversine_miles(a, b) <= tolerance_miles for a, b in zip(points, other, strict=True)
            )
            for _, other in kept
        )
        if not is_duplicate:
            kept.append((route, points))
    return [route for route, _ in kept]
