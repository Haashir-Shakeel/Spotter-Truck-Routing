"""Builds the real provider-backed services from Django settings.

One pooled httpx client is shared across requests in a process.
"""

from datetime import datetime
from functools import cache

import httpx
from django.conf import settings

from apps.routing.domain.types import Coordinate, GeocodedPlace

from .corridor_forecast import CorridorForecaster
from .demo_weather import DemoWeatherProvider
from .geocoding import MapboxGeocodingProvider
from .routing_provider import MapboxRoutingProvider
from .timezones import OpenMeteoTimezoneProvider
from .trip_planner import TripPlannerService
from .weather_provider import OpenMeteoWeatherProvider

USER_AGENT = "spotter-route-planner/0.1"


@cache
def http_client() -> httpx.Client:
    return httpx.Client(
        timeout=settings.PROVIDER_TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT},
    )


def build_geocoder() -> MapboxGeocodingProvider:
    return MapboxGeocodingProvider(
        http_client(), settings.MAPBOX_ACCESS_TOKEN, max_retries=settings.PROVIDER_MAX_RETRIES
    )


def build_weather() -> OpenMeteoWeatherProvider:
    return OpenMeteoWeatherProvider(
        http_client(), settings.OPEN_METEO_BASE_URL, max_retries=settings.PROVIDER_MAX_RETRIES
    )


def demo_weather_for_trip(
    origin: GeocodedPlace, destination: GeocodedPlace, departure_at: datetime
) -> DemoWeatherProvider:
    return DemoWeatherProvider(
        (origin.lon, origin.lat), (destination.lon, destination.lat), departure_at
    )


def build_corridor_forecaster(
    demo_trip: tuple[Coordinate, Coordinate, datetime] | None = None,
) -> CorridorForecaster:
    """Live weather, or the same synthetic storms the analysis used when ``demo_trip`` is set."""
    if demo_trip is not None:
        return CorridorForecaster(DemoWeatherProvider(*demo_trip))
    return CorridorForecaster(build_weather())


def build_trip_planner(*, demo: bool = False) -> TripPlannerService:
    retries = settings.PROVIDER_MAX_RETRIES
    return TripPlannerService(
        geocoder=build_geocoder(),
        router=MapboxRoutingProvider(
            http_client(), settings.MAPBOX_ACCESS_TOKEN, max_retries=retries
        ),
        weather=build_weather(),
        timezones=OpenMeteoTimezoneProvider(
            http_client(), settings.OPEN_METEO_BASE_URL, max_retries=retries
        ),
        weather_for_trip=demo_weather_for_trip if demo else None,
        max_departure_days_ahead=settings.TRIP_MAX_DEPARTURE_DAYS_AHEAD,
    )
