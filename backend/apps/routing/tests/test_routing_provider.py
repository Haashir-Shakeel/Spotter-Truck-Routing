import httpx
import pytest

from apps.routing.domain.types import RouteOption
from apps.routing.services.errors import ProviderConfigurationError, ProviderResponseError
from apps.routing.services.routing_provider import (
    MapboxRoutingProvider,
    deduplicate_routes,
    parse_mapbox_directions,
)

from .helpers import load_fixture

CHICAGO = (-87.6298, 41.8781)
DETROIT = (-83.0458, 42.3314)


def test_fetches_and_normalizes_alternatives(mock_client) -> None:
    body = load_fixture("mapbox_directions_synthetic.json")
    client, transport = mock_client(lambda r: httpx.Response(200, json=body))

    routes = MapboxRoutingProvider(client, "tok").get_routes(CHICAGO, DETROIT)

    assert [r.route_id for r in routes] == ["route_1", "route_2", "route_3"]
    first = routes[0]
    assert first.distance_miles == pytest.approx(455000 / 1609.344)
    assert first.duration_seconds == 14200
    assert first.coordinates[0] == CHICAGO and first.coordinates[-1] == DETROIT
    assert first.cumulative_durations == (0, 3600, 6600, 9800, 14200)

    request = transport.requests[0]
    assert "-87.629800,41.878100;-83.045800,42.331400" in request.url.path
    params = request.url.params
    assert params["alternatives"] == "true"
    assert params["geometries"] == "geojson"
    assert params["overview"] == "full"
    assert params["annotations"] == "duration"
    assert params["access_token"] == "tok"


def test_missing_token_is_a_configuration_error() -> None:
    with pytest.raises(ProviderConfigurationError):
        MapboxRoutingProvider(httpx.Client(), "")


@pytest.mark.parametrize("code", ["NoRoute", "NoSegment"])
def test_no_route_returns_empty_list(code: str) -> None:
    assert parse_mapbox_directions({"code": code, "routes": []}) == []


def test_other_error_codes_are_rejected() -> None:
    with pytest.raises(ProviderResponseError):
        parse_mapbox_directions({"code": "InvalidInput", "message": "bad"})


def test_malformed_route_is_rejected() -> None:
    with pytest.raises(ProviderResponseError):
        parse_mapbox_directions({"code": "Ok", "routes": [{"distance": 1}]})


def test_annotations_that_do_not_match_geometry_fall_back_to_none() -> None:
    body = load_fixture("mapbox_directions_synthetic.json")
    body["routes"][0]["legs"][0]["annotation"]["duration"] = [10.0]

    routes = parse_mapbox_directions(body)

    assert routes[0].cumulative_durations is None


def test_fewer_than_three_routes_are_returned_as_is() -> None:
    body = load_fixture("mapbox_directions_synthetic.json")
    body["routes"] = body["routes"][:2]

    assert len(parse_mapbox_directions(body)) == 2


# --- deduplication ---------------------------------------------------------------------------


def option(route_id: str, coords: list[tuple[float, float]]) -> RouteOption:
    return RouteOption(
        route_id=route_id, coordinates=tuple(coords), distance_miles=100, duration_seconds=3600
    )


def test_same_road_with_different_vertices_is_a_duplicate() -> None:
    a = option("a", [(0.0, 0.0), (1.0, 0.0)])
    b = option("b", [(0.0, 0.0), (0.3, 0.0), (0.7, 0.0), (1.0, 0.0)])

    assert [r.route_id for r in deduplicate_routes([a, b])] == ["a"]


def test_genuinely_different_roads_are_kept() -> None:
    a = option("a", [(0.0, 0.0), (1.0, 0.0)])
    b = option("b", [(0.0, 0.0), (0.5, 0.3), (1.0, 0.0)])  # ~20 miles off at the midpoint

    assert [r.route_id for r in deduplicate_routes([a, b])] == ["a", "b"]


def test_fixture_routes_are_all_distinct() -> None:
    routes = parse_mapbox_directions(load_fixture("mapbox_directions_synthetic.json"))
    assert len(deduplicate_routes(routes)) == 3


def test_via_waypoint_requests_one_route_through_it(mock_client) -> None:
    body = load_fixture("mapbox_directions_synthetic.json")
    client, transport = mock_client(lambda r: httpx.Response(200, json=body))
    via = (-85.5, 42.9)

    routes = MapboxRoutingProvider(client, "tok").get_routes(CHICAGO, DETROIT, via=via)

    request = transport.requests[0]
    assert "-87.629800,41.878100;-85.500000,42.900000;-83.045800,42.331400" in request.url.path
    assert request.url.params["alternatives"] == "false"
    assert all(route.via == via for route in routes)
