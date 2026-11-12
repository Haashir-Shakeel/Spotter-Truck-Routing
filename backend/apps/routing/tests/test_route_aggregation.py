import pytest

from apps.routing.domain.risk_levels import RiskLevel
from apps.routing.domain.types import CheckpointRisk
from apps.routing.services.route_aggregation import summarize_route_risk

L, M, H = RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH


def cps(*points: tuple[float, RiskLevel | None]) -> list[CheckpointRisk]:
    return [CheckpointRisk(distance_miles=d, risk=r) for d, r in points]


def test_segment_takes_higher_endpoint_risk() -> None:
    # Example from the plan: 25 mi L->M, 25 mi M->H, 12 mi H->L
    summary = summarize_route_risk(
        route_id="a",
        checkpoints=cps((0, L), (25, M), (50, H), (62, L)),
        duration_seconds=3600,
    )

    assert summary.miles_by_level[M] == 25
    assert summary.high_miles == 37
    assert summary.miles_by_level[L] == 0
    assert summary.distance_miles == 62
    assert summary.max_risk == H
    assert summary.average_risk == pytest.approx((25 * 1 + 37 * 2) / 62)


def test_risk_miles_sum_to_route_distance() -> None:
    summary = summarize_route_risk(
        route_id="a",
        checkpoints=cps((0, L), (25, L), (50, M), (75, H), (100, L), (112, L)),
        duration_seconds=7200,
    )

    assert sum(summary.miles_by_level.values()) == pytest.approx(112)
    assert summary.is_complete


def test_missing_forecast_counts_as_unavailable_not_low() -> None:
    summary = summarize_route_risk(
        route_id="a",
        checkpoints=cps((0, L), (25, None), (50, L), (60, L)),
        duration_seconds=3600,
    )

    assert summary.unavailable_miles == 50
    assert summary.miles_by_level[L] == 10
    assert not summary.is_complete


def test_all_missing_has_no_max_risk() -> None:
    summary = summarize_route_risk(
        route_id="a", checkpoints=cps((0, None), (10, None)), duration_seconds=600
    )

    assert summary.max_risk is None
    assert summary.average_risk == 0.0
    assert summary.unavailable_miles == 10


def test_label_defaults_to_route_id() -> None:
    summary = summarize_route_risk(
        route_id="a", checkpoints=cps((0, L), (1, L)), duration_seconds=1
    )
    assert summary.label == "a"


@pytest.mark.parametrize(
    "points",
    [((0, L),), ((0, L), (10, L), (5, L))],
    ids=["single-checkpoint", "out-of-order"],
)
def test_invalid_checkpoints_rejected(points: tuple[tuple[float, RiskLevel], ...]) -> None:
    with pytest.raises(ValueError):
        summarize_route_risk(route_id="a", checkpoints=cps(*points), duration_seconds=1)
