"""Place search via Mapbox Geocoding v6, normalized to ``GeocodedPlace``."""

from typing import Any, Protocol

import httpx

from apps.routing.domain.types import GeocodedPlace

from .errors import ProviderConfigurationError, ProviderResponseError
from .http import get_json

MAPBOX_GEOCODE_URL = "https://api.mapbox.com/search/geocode/v6/forward"
PROVIDER = "Mapbox Geocoding"
MAX_QUERY_LENGTH = 200


class GeocodingProvider(Protocol):
    def search(self, query: str, *, limit: int = 5) -> list[GeocodedPlace]: ...


class MapboxGeocodingProvider:
    def __init__(
        self,
        client: httpx.Client,
        access_token: str,
        *,
        country: str = "us,ca",
        max_retries: int = 2,
    ) -> None:
        if not access_token:
            raise ProviderConfigurationError(PROVIDER, "MAPBOX_ACCESS_TOKEN is not set")
        self._client = client
        self._token = access_token
        self._country = country
        self._max_retries = max_retries

    def search(self, query: str, *, limit: int = 5) -> list[GeocodedPlace]:
        query = query.strip()
        if not query:
            raise ValueError("Search text must not be empty.")
        if len(query) > MAX_QUERY_LENGTH:
            raise ValueError(f"Search text must be at most {MAX_QUERY_LENGTH} characters.")
        if not 1 <= limit <= 10:
            raise ValueError("limit must be between 1 and 10.")

        body = get_json(
            self._client,
            MAPBOX_GEOCODE_URL,
            params={
                "q": query,
                "limit": limit,
                "country": self._country,
                "autocomplete": "true",
                "access_token": self._token,
            },
            provider=PROVIDER,
            max_retries=self._max_retries,
        )
        return parse_mapbox_geocode(body)


def parse_mapbox_geocode(body: Any) -> list[GeocodedPlace]:
    if not isinstance(body, dict) or not isinstance(body.get("features"), list):
        raise ProviderResponseError(PROVIDER, "unexpected response shape")

    places: list[GeocodedPlace] = []
    for feature in body["features"]:
        try:
            lon, lat = feature["geometry"]["coordinates"][:2]
            props = feature.get("properties", {})
            name = props.get("full_address") or props.get("name") or ""
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderResponseError(PROVIDER, "malformed place") from exc
        if name:
            places.append(GeocodedPlace(name=name, lon=float(lon), lat=float(lat)))
    return places
