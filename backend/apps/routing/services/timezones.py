"""IANA time zone names for coordinates, so trip times can be shown in the trip's local time.

Open-Meteo resolves ``timezone=auto`` from coordinates and returns the zone name (e.g.
``America/Chicago``) without any weather variables, so one small batched request covers the
origin and destination. Names are validated against the local tz database; anything unknown is
returned as None and the client falls back to the viewer's own time zone.
"""

from collections.abc import Sequence
from typing import Any, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from apps.routing.domain.types import Coordinate

from .errors import ProviderResponseError
from .http import get_json

PROVIDER = "Open-Meteo"


class TimezoneProvider(Protocol):
    def timezones(self, points: Sequence[Coordinate]) -> list[str | None]: ...


def _valid_zone(name: Any) -> str | None:
    if not isinstance(name, str) or not name or name == "GMT":
        return None
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    return name


class OpenMeteoTimezoneProvider:
    def __init__(
        self,
        client: httpx.Client,
        base_url: str = "https://api.open-meteo.com/v1",
        *,
        max_retries: int = 2,
    ) -> None:
        self._client = client
        self._url = f"{base_url.rstrip('/')}/forecast"
        self._max_retries = max_retries

    def timezones(self, points: Sequence[Coordinate]) -> list[str | None]:
        if not points:
            return []
        body = get_json(
            self._client,
            self._url,
            params={
                "latitude": ",".join(f"{lat:.4f}" for _, lat in points),
                "longitude": ",".join(f"{lon:.4f}" for lon, _ in points),
                "timezone": "auto",
                "forecast_days": 1,
            },
            provider=PROVIDER,
            max_retries=self._max_retries,
        )
        locations = [body] if isinstance(body, dict) else body
        if not isinstance(locations, list) or len(locations) != len(points):
            raise ProviderResponseError(PROVIDER, "number of locations does not match the request")
        return [
            _valid_zone(loc.get("timezone")) if isinstance(loc, dict) else None for loc in locations
        ]
