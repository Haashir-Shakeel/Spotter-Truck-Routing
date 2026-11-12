"""In-memory providers for offline tests of the trip planner and API."""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

from apps.routing.domain.types import Coordinate, GeocodedPlace, HourlyForecast, RouteOption
from apps.routing.services.geo import cumulative_distances_miles
from apps.routing.services.trip_planner import TripPlannerService

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)

# Three distinct ~105-mile routes between two points on latitude 40: straight, north, south.
ORIGIN = GeocodedPlace("Origin City", -90.0, 40.0)
DESTINATION = GeocodedPlace("Destination City", -88.0, 40.0)


def make_route(route_id: str, via: list[Coordinate], mph: float = 60.0) -> RouteOption:
    coords = ((ORIGIN.lon, ORIGIN.lat), *via, (DESTINATION.lon, DESTINATION.lat))
    miles = cumulative_distances_miles(coords)
    return RouteOption(
        route_id=route_id,
        coordinates=coords,
        distance_miles=miles[-1],
        duration_seconds=miles[-1] / mph * 3600,
        cumulative_durations=tuple(m / mph * 3600 for m in miles),
    )


STRAIGHT = make_route("p1", [(-89.0, 40.0)])
NORTH = make_route("p2", [(-89.0, 40.5)])
SOUTH = make_route("p3", [(-89.0, 39.5)], mph=50)


class FakeGeocoder:
    def __init__(self, places: dict[str, GeocodedPlace] | None = None) -> None:
        if places is None:
            places = {"Origin": ORIGIN, "Destination": DESTINATION}
        self.places = places
        self.queries: list[str] = []

    def search(self, query: str, *, limit: int = 5) -> list[GeocodedPlace]:
        self.queries.append(query)
        place = self.places.get(query)
        return [place][:limit] if place else []


class FakeRouter:
    def __init__(self, routes: Sequence[RouteOption] = (STRAIGHT, NORTH, SOUTH)) -> None:
        self.routes = list(routes)
        self.calls: list[tuple[Coordinate, Coordinate]] = []

    def get_routes(self, origin: Coordinate, destination: Coordinate) -> list[RouteOption]:
        self.calls.append((origin, destination))
        return list(self.routes)


# (lon, lat, hour) -> (wind_mph, rain_in_hr, snow_in_hr), or None when unavailable
WeatherFn = Callable[[float, float, datetime], tuple[float, float, float] | None]


def calm(lon: float, lat: float, when: datetime) -> tuple[float, float, float]:
    return (5.0, 0.0, 0.0)


class FakeWeather:
    def __init__(self, fn: WeatherFn = calm) -> None:
        self.fn = fn
        self.calls: list[tuple[list[Coordinate], datetime, datetime]] = []

    def hourly_forecasts(
        self, points: Sequence[Coordinate], start: datetime, end: datetime
    ) -> list[HourlyForecast]:
        self.calls.append((list(points), start, end))
        hours = int((end - start).total_seconds() // 3600) + 1
        times = tuple(start + timedelta(hours=h) for h in range(hours))
        forecasts = []
        for lon, lat in points:
            values = [self.fn(lon, lat, t) for t in times]
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


def make_planner(
    *,
    geocoder: FakeGeocoder | None = None,
    router: FakeRouter | None = None,
    weather: FakeWeather | None = None,
) -> TripPlannerService:
    return TripPlannerService(
        geocoder=geocoder or FakeGeocoder(),
        router=router or FakeRouter(),
        weather=weather or FakeWeather(),
        clock=lambda: NOW,
    )
