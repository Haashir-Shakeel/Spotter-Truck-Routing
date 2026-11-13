"""Builds the real provider-backed services from Django settings.

One pooled httpx client is shared across requests in a process.
"""

from functools import cache

import httpx
from django.conf import settings

from .corridor_forecast import CorridorForecaster
from .geocoding import MapboxGeocodingProvider
from .routing_provider import MapboxRoutingProvider
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


def build_corridor_forecaster() -> CorridorForecaster:
    return CorridorForecaster(build_weather())


def build_trip_planner() -> TripPlannerService:
    retries = settings.PROVIDER_MAX_RETRIES
    return TripPlannerService(
        geocoder=build_geocoder(),
        router=MapboxRoutingProvider(
            http_client(), settings.MAPBOX_ACCESS_TOKEN, max_retries=retries
        ),
        weather=build_weather(),
        max_departure_days_ahead=settings.TRIP_MAX_DEPARTURE_DAYS_AHEAD,
    )
