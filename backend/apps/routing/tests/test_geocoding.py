import httpx
import pytest

from apps.routing.domain.types import GeocodedPlace
from apps.routing.services.errors import ProviderConfigurationError, ProviderResponseError
from apps.routing.services.geocoding import MapboxGeocodingProvider, parse_mapbox_geocode

from .helpers import load_fixture


def test_search_returns_places(mock_client) -> None:
    body = load_fixture("mapbox_geocode_synthetic.json")
    client, transport = mock_client(lambda r: httpx.Response(200, json=body))

    places = MapboxGeocodingProvider(client, "tok").search("  Chicago ", limit=2)

    assert places == [
        GeocodedPlace(name="Chicago, Illinois, United States", lon=-87.6298, lat=41.8781),
        GeocodedPlace(name="Chicago Heights", lon=-89.39, lat=43.07),
    ]
    params = transport.requests[0].url.params
    assert params["q"] == "Chicago"
    assert params["limit"] == "2"
    assert params["country"] == "us,ca"
    assert params["access_token"] == "tok"


@pytest.mark.parametrize(("query", "limit"), [("", 5), ("   ", 5), ("x" * 201, 5), ("ok", 0)])
def test_invalid_search_rejected_without_calling_provider(mock_client, query, limit) -> None:
    client, transport = mock_client(lambda r: httpx.Response(200, json={}))

    with pytest.raises(ValueError):
        MapboxGeocodingProvider(client, "tok").search(query, limit=limit)
    assert transport.requests == []


def test_missing_token_is_a_configuration_error() -> None:
    with pytest.raises(ProviderConfigurationError):
        MapboxGeocodingProvider(httpx.Client(), "")


def test_no_matches_is_an_empty_list() -> None:
    assert parse_mapbox_geocode({"type": "FeatureCollection", "features": []}) == []


def test_unexpected_shape_is_rejected() -> None:
    with pytest.raises(ProviderResponseError):
        parse_mapbox_geocode({"message": "Not Found"})
