import uuid

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.routing.models import TripAnalysisRecord
from apps.routing.services import providers
from apps.routing.services.errors import ProviderUnavailableError

from .fakes import FakeGeocoder, FakeRouter, make_planner

pytestmark = pytest.mark.django_db

VALID = {
    "origin": {"name": "Origin"},
    "destination": {"name": "Destination"},
    "departure_at": "2026-11-13T07:00:00-06:00",  # 13:00 UTC, one hour after the fake clock
    "load_weight_lb": 35000,
    "checkpoint_interval_miles": 25,
}


@pytest.fixture(autouse=True)
def fake_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(providers, "build_trip_planner", make_planner)
    monkeypatch.setattr(providers, "build_geocoder", FakeGeocoder)


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def analyze(client: APIClient, payload: dict):
    return client.post(reverse("trip-analyze"), payload, format="json")


def test_analyze_returns_routes_checkpoints_and_recommendation(client: APIClient) -> None:
    response = analyze(client, VALID)

    assert response.status_code == 201
    body = response.json()
    assert uuid.UUID(body["analysis_id"])
    assert body["status"] == "complete"
    assert body["recommendation"]["recommended_route_id"] == "A"
    assert body["recommendation"]["status"] == "route_available"
    assert [r["id"] for r in body["routes"]] == ["A", "B", "C"]

    route = body["routes"][0]
    assert route["geometry"]["type"] == "LineString"
    assert route["risk_summary"]["max_risk"] == "LOW"
    assert route["risk_summary"]["complete"] is True
    checkpoint = route["checkpoints"][0]
    assert checkpoint["arrival_at"] == "2026-11-13T13:00:00+00:00"
    assert checkpoint["risk"] == "LOW"
    assert set(checkpoint["weather"]) == {"wind_mph", "rain_in_per_hour", "snow_in_per_hour"}
    assert TripAnalysisRecord.objects.count() == 1


def test_saved_analysis_can_be_fetched(client: APIClient) -> None:
    created = analyze(client, VALID).json()

    response = client.get(reverse("trip-detail", args=[created["analysis_id"]]))

    assert response.status_code == 200
    assert response.json() == created


def test_unknown_analysis_is_404(client: APIClient) -> None:
    response = client.get(reverse("trip-detail", args=[uuid.uuid4()]))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"checkpoint_interval_miles": 15}, "checkpoint_interval_miles"),
        ({"load_weight_lb": 0}, "load_weight_lb"),
        ({"load_weight_lb": 1_000_000}, "load_weight_lb"),
        ({"departure_at": "2026-11-13T07:00:00"}, "departure_at"),  # no offset
        ({"departure_at": "tomorrow"}, "departure_at"),
        ({"destination": {"name": ""}}, "destination"),
        ({"origin": {"name": "X", "lon": -90}}, "origin"),  # lon without lat
        ({"origin": {"name": "X", "lon": -200, "lat": 40}}, "origin"),
    ],
)
def test_invalid_requests_are_400_with_field_errors(client: APIClient, change: dict, field: str):
    response = analyze(client, {**VALID, **change})

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert field in error["details"]
    assert TripAnalysisRecord.objects.count() == 0


def test_missing_field_is_400(client: APIClient) -> None:
    payload = {k: v for k, v in VALID.items() if k != "destination"}
    assert analyze(client, payload).status_code == 400


def test_trip_input_errors_use_their_own_codes(client: APIClient) -> None:
    response = analyze(client, {**VALID, "destination": {"name": "Atlantis"}})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "LOCATION_NOT_FOUND"


def test_no_route_is_422(client: APIClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        providers, "build_trip_planner", lambda: make_planner(router=FakeRouter([]))
    )
    response = analyze(client, VALID)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_ROUTE_FOUND"


def test_provider_outage_is_503_and_nothing_is_saved(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class DownRouter(FakeRouter):
        def get_routes(self, origin, destination):
            raise ProviderUnavailableError("Mapbox Directions", "request timed out")

    monkeypatch.setattr(providers, "build_trip_planner", lambda: make_planner(router=DownRouter()))
    response = analyze(client, VALID)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
    assert TripAnalysisRecord.objects.count() == 0


def test_place_search(client: APIClient) -> None:
    response = client.get(reverse("place-search"), {"q": "Origin"})

    assert response.status_code == 200
    assert response.json() == {"results": [{"name": "Origin City", "lon": -90.0, "lat": 40.0}]}


def test_place_search_requires_query(client: APIClient) -> None:
    response = client.get(reverse("place-search"))

    assert response.status_code == 400
    assert "q" in response.json()["error"]["details"]
