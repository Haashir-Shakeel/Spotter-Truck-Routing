import httpx
import pytest

from apps.routing.services.errors import ProviderResponseError, ProviderUnavailableError
from apps.routing.services.timezones import OpenMeteoTimezoneProvider

from .fakes import FakeTimezones, make_planner
from .test_trip_planner import trip

DALLAS = (-96.8, 32.78)
PHOENIX = (-112.07, 33.45)


def test_returns_iana_zones_per_point(mock_client) -> None:
    body = [
        {"timezone": "America/Chicago", "utc_offset_seconds": -21600},
        {"timezone": "America/Phoenix", "utc_offset_seconds": -25200},
    ]
    client, transport = mock_client(lambda r: httpx.Response(200, json=body))

    zones = OpenMeteoTimezoneProvider(client).timezones([DALLAS, PHOENIX])

    assert zones == ["America/Chicago", "America/Phoenix"]
    params = transport.requests[0].url.params
    assert params["timezone"] == "auto"
    assert params["latitude"] == "32.7800,33.4500"
    assert params["longitude"] == "-96.8000,-112.0700"
    assert "hourly" not in params  # no weather variables needed


def test_unknown_or_generic_zones_become_none(mock_client) -> None:
    body = [{"timezone": "Mars/Olympus_Mons"}, {"timezone": "GMT"}]
    client, _ = mock_client(lambda r: httpx.Response(200, json=body))

    assert OpenMeteoTimezoneProvider(client).timezones([DALLAS, PHOENIX]) == [None, None]


def test_location_count_mismatch_is_rejected(mock_client) -> None:
    client, _ = mock_client(lambda r: httpx.Response(200, json=[{"timezone": "America/Chicago"}]))

    with pytest.raises(ProviderResponseError):
        OpenMeteoTimezoneProvider(client).timezones([DALLAS, PHOENIX])


def test_planner_reports_trip_time_zones() -> None:
    planner = make_planner(timezones=FakeTimezones(["America/Chicago", "America/Phoenix"]))

    analysis = planner.analyze_trip(trip())

    assert analysis.origin_timezone == "America/Chicago"
    assert analysis.destination_timezone == "America/Phoenix"


def test_time_zone_outage_does_not_fail_the_trip() -> None:
    class DownTimezones(FakeTimezones):
        def timezones(self, points):
            raise ProviderUnavailableError("Open-Meteo", "timed out")

    analysis = make_planner(timezones=DownTimezones()).analyze_trip(trip())

    assert analysis.origin_timezone is None
    assert analysis.destination_timezone is None
    assert analysis.routes  # analysis still completes
