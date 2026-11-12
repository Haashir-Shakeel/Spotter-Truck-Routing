import pytest

from apps.routing.domain.risk_levels import RiskLevel
from apps.routing.domain.types import (
    IneligibilityReason,
    RecommendationStatus,
    RouteRiskSummary,
)
from apps.routing.services.recommendation import recommend_route


def route(
    route_id: str,
    *,
    severe: float = 0,
    high: float = 0,
    no_travel: float = 0,
    average: float = 0.0,
    hours: float = 5,
    unavailable: float = 0,
) -> RouteRiskSummary:
    miles = dict.fromkeys(RiskLevel, 0.0)
    miles[RiskLevel.SEVERE] = severe
    miles[RiskLevel.HIGH] = high
    miles[RiskLevel.NO_TRAVEL] = no_travel
    miles[RiskLevel.LOW] = 100
    return RouteRiskSummary(
        route_id=route_id,
        label=f"Route {route_id}",
        distance_miles=100 + severe + high + no_travel + unavailable,
        duration_seconds=hours * 3600,
        miles_by_level=miles,
        unavailable_miles=unavailable,
        average_risk=average,
        max_risk=RiskLevel.LOW,
    )


def test_fewer_severe_miles_wins_even_if_much_slower() -> None:
    result = recommend_route(
        [route("A", severe=25, hours=4), route("B", severe=0, high=50, hours=9)]
    )

    assert result.recommended_route_id == "B"
    assert result.ranked_route_ids == ["B", "A"]
    assert "0.0 Severe miles versus 25.0 on Route A" in result.explanation
    assert "Route A is 5 h 0 min faster" in result.explanation


def test_equal_severe_then_fewer_high_wins() -> None:
    result = recommend_route([route("A", severe=10, high=30), route("B", severe=10, high=5)])

    assert result.recommended_route_id == "B"
    assert "5.0 High-risk miles versus 30.0" in result.explanation


def test_equal_severe_and_high_then_lower_average_wins() -> None:
    result = recommend_route(
        [route("A", high=5, average=0.6, hours=3), route("B", high=5, average=0.4, hours=6)]
    )

    assert result.recommended_route_id == "B"
    assert "lower average risk (0.40 versus 0.60)" in result.explanation


def test_all_risk_equal_then_shortest_time_wins() -> None:
    result = recommend_route([route("A", hours=6), route("B", hours=5.5)])

    assert result.recommended_route_id == "B"
    assert "30 min faster" in result.explanation


def test_full_tie_is_deterministic_by_route_id() -> None:
    first = recommend_route([route("B"), route("A")])
    second = recommend_route([route("A"), route("B")])

    assert first.recommended_route_id == second.recommended_route_id == "A"


def test_float_noise_does_not_decide_ranking() -> None:
    result = recommend_route(
        [route("A", severe=0.1 + 0.2, hours=4), route("B", severe=0.3, hours=5)]
    )

    assert result.recommended_route_id == "A"


def test_no_travel_route_is_ineligible_even_if_otherwise_best() -> None:
    result = recommend_route([route("A", no_travel=5, hours=3), route("B", severe=40, hours=8)])

    assert result.status is RecommendationStatus.ROUTE_AVAILABLE
    assert result.recommended_route_id == "B"
    assert result.ineligible == {"A": IneligibilityReason.NO_TRAVEL}
    assert result.ranked_route_ids == ["B", "A"]
    assert "Route A was excluded: 5.0 No Travel miles." in result.explanation


def test_incomplete_forecast_route_is_ineligible() -> None:
    result = recommend_route([route("A", unavailable=20), route("B", high=10)])

    assert result.recommended_route_id == "B"
    assert result.ineligible == {"A": IneligibilityReason.INCOMPLETE_FORECAST}


def test_all_routes_no_travel_reports_no_safe_route() -> None:
    result = recommend_route(
        [route("A", no_travel=1), route("B", no_travel=2), route("C", no_travel=3)]
    )

    assert result.status is RecommendationStatus.NO_SAFE_ROUTE
    assert result.recommended_route_id is None
    assert result.ranked_route_ids == ["A", "B", "C"]


def test_single_route_is_recommended_with_its_own_numbers() -> None:
    result = recommend_route([route("A", severe=2, high=3)])

    assert result.recommended_route_id == "A"
    assert result.explanation == "Route A is recommended with 2.0 Severe and 3.0 High-risk miles."


@pytest.mark.parametrize("routes", [[], [route("A"), route("A")]], ids=["empty", "duplicate-ids"])
def test_invalid_input_rejected(routes: list[RouteRiskSummary]) -> None:
    with pytest.raises(ValueError):
        recommend_route(routes)
