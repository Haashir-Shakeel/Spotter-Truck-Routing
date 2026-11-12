from datetime import UTC, datetime

import httpx
import pytest

from apps.routing.services.errors import ProviderResponseError
from apps.routing.services.weather_provider import OpenMeteoWeatherProvider, parse_open_meteo

from .helpers import load_fixture

CHICAGO = (-87.6298, 41.8781)
DETROIT = (-83.0458, 42.3314)
START = datetime(2026, 11, 13, 12, tzinfo=UTC)
END = datetime(2026, 11, 13, 17, tzinfo=UTC)


def location(times: list[int], value: float | None = 0.0, **unit_overrides: str) -> dict:
    units = {
        "time": "unixtime",
        "wind_speed_10m": "mp/h",
        "rain": "inch",
        "showers": "inch",
        "snowfall": "inch",
        **unit_overrides,
    }
    series = [value] * len(times)
    return {
        "hourly_units": units,
        "hourly": {
            "time": times,
            "wind_speed_10m": series,
            "rain": series,
            "showers": series,
            "snowfall": series,
        },
    }


def test_parses_real_open_meteo_response() -> None:
    # Fixture is a real Open-Meteo response captured 2026-11-12 for Chicago and Detroit.
    forecasts = parse_open_meteo(load_fixture("open_meteo_two_points.json"), [CHICAGO, DETROIT])

    chicago = forecasts[0]
    assert (chicago.lon, chicago.lat) == CHICAGO  # requested point, not the provider grid cell
    assert chicago.times[0] == START
    assert chicago.times[-1] == END
    assert len(chicago.times) == 6
    assert chicago.wind_mph[1] == 11.7
    assert chicago.rain_in_per_hour[3] == pytest.approx(0.067)  # rain + showers
    assert chicago.snow_in_per_hour[3] == pytest.approx(0.524)


def test_requests_units_and_window(mock_client) -> None:
    body = load_fixture("open_meteo_two_points.json")
    client, transport = mock_client(lambda r: httpx.Response(200, json=body))

    OpenMeteoWeatherProvider(client).hourly_forecasts([CHICAGO, DETROIT], START, END)

    params = transport.requests[0].url.params
    assert params["latitude"] == "41.8781,42.3314"
    assert params["longitude"] == "-87.6298,-83.0458"
    assert params["hourly"] == "wind_speed_10m,rain,showers,snowfall"
    assert params["wind_speed_unit"] == "mph"
    assert params["precipitation_unit"] == "inch"
    assert params["timezone"] == "GMT"
    assert params["start_hour"] == "2026-11-13T12:00"
    assert params["end_hour"] == "2026-11-13T17:00"


def test_points_are_batched_and_order_is_kept(mock_client) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        count = len(request.url.params["latitude"].split(","))
        return httpx.Response(200, json=[location([1794571200]) for _ in range(count)])

    client, transport = mock_client(respond)
    points = [(-90 + i * 0.01, 40.0) for i in range(250)]

    forecasts = OpenMeteoWeatherProvider(client, batch_size=100).hourly_forecasts(
        points, START, END
    )

    assert len(transport.requests) == 3
    assert [(f.lon, f.lat) for f in forecasts] == points


def test_single_location_object_is_accepted() -> None:
    forecasts = parse_open_meteo(location([1794571200]), [CHICAGO])
    assert len(forecasts) == 1


def test_missing_values_stay_missing() -> None:
    forecasts = parse_open_meteo(location([1794571200], value=None), [CHICAGO])
    assert forecasts[0].wind_mph == (None,)
    assert forecasts[0].rain_in_per_hour == (None,)


def test_unexpected_units_are_rejected_not_converted() -> None:
    with pytest.raises(ProviderResponseError):
        parse_open_meteo(location([1794571200], snowfall="cm"), [CHICAGO])


def test_location_count_mismatch_is_rejected() -> None:
    with pytest.raises(ProviderResponseError):
        parse_open_meteo([location([1794571200])], [CHICAGO, DETROIT])


def test_ragged_series_is_rejected() -> None:
    body = location([1794571200, 1794574800])
    body["hourly"]["rain"] = [0.0]
    with pytest.raises(ProviderResponseError):
        parse_open_meteo(body, [CHICAGO])


def test_window_must_be_timezone_aware(mock_client) -> None:
    client, _ = mock_client(lambda r: httpx.Response(200, json=[]))
    with pytest.raises(ValueError):
        OpenMeteoWeatherProvider(client).hourly_forecasts(
            [CHICAGO], datetime(2026, 11, 13, 12), END
        )
