"""Pick the recommended route using the assessment's strict priority order.

1. Fewest Severe miles  2. Fewest High miles  3. Lowest average risk  4. Shortest travel time

Compared lexicographically, so time can never outweigh Severe miles. Routes with any No Travel
miles, or with incomplete forecast coverage, are not eligible to be recommended as safe.
"""

from collections.abc import Sequence

from apps.routing.domain.types import (
    IneligibilityReason,
    Recommendation,
    RecommendationStatus,
    RouteRiskSummary,
)

# Rounding keeps float noise from deciding ties; route_id is a final, stable technical tiebreaker.
_MILES_PRECISION = 2
_AVERAGE_PRECISION = 4


def rank_key(route: RouteRiskSummary) -> tuple[float, float, float, float, str]:
    return (
        round(route.severe_miles, _MILES_PRECISION),
        round(route.high_miles, _MILES_PRECISION),
        round(route.average_risk, _AVERAGE_PRECISION),
        route.duration_seconds,
        route.route_id,
    )


def _ineligibility(route: RouteRiskSummary) -> IneligibilityReason | None:
    if route.no_travel_miles > 0:
        return IneligibilityReason.NO_TRAVEL
    if not route.is_complete:
        return IneligibilityReason.INCOMPLETE_FORECAST
    return None


def _format_duration(seconds: float) -> str:
    minutes = round(abs(seconds) / 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min" if hours else f"{minutes} min"


def _compare(best: RouteRiskSummary, other: RouteRiskSummary) -> str:
    """Explain the first criterion on which ``best`` beats ``other``, using real numbers."""
    best_key, other_key = rank_key(best), rank_key(other)

    if best_key[0] != other_key[0]:
        clause = (
            f"it has {best.severe_miles:.1f} Severe miles versus "
            f"{other.severe_miles:.1f} on {other.label}"
        )
    elif best_key[1] != other_key[1]:
        clause = (
            f"it ties {other.label} on Severe miles but has {best.high_miles:.1f} "
            f"High-risk miles versus {other.high_miles:.1f}"
        )
    elif best_key[2] != other_key[2]:
        clause = (
            f"it ties {other.label} on Severe and High miles but has a lower average risk "
            f"({best.average_risk:.2f} versus {other.average_risk:.2f})"
        )
    elif best_key[3] != other_key[3]:
        faster = _format_duration(other.duration_seconds - best.duration_seconds)
        return f"it ties {other.label} on every risk measure and is {faster} faster"
    else:
        return f"it is tied with {other.label} on every measure"

    if other.duration_seconds < best.duration_seconds:
        gap = _format_duration(best.duration_seconds - other.duration_seconds)
        clause += f" ({other.label} is {gap} faster, but weather exposure takes priority)"
    return clause


def _explain(
    best: RouteRiskSummary,
    ranked_eligible: list[RouteRiskSummary],
    ineligible_routes: list[tuple[RouteRiskSummary, IneligibilityReason]],
) -> str:
    comparisons = [_compare(best, other) for other in ranked_eligible[1:]]
    if comparisons:
        text = f"{best.label} is recommended because " + "; ".join(comparisons) + "."
    else:
        text = (
            f"{best.label} is recommended with {best.severe_miles:.1f} Severe and "
            f"{best.high_miles:.1f} High-risk miles."
        )

    for route, reason in ineligible_routes:
        if reason is IneligibilityReason.NO_TRAVEL:
            text += f" {route.label} was excluded: {route.no_travel_miles:.1f} No Travel miles."
        else:
            text += (
                f" {route.label} was excluded: forecast unavailable for "
                f"{route.unavailable_miles:.1f} miles."
            )
    return text


def recommend_route(routes: Sequence[RouteRiskSummary]) -> Recommendation:
    if not routes:
        raise ValueError("At least one route is required to make a recommendation.")

    by_id = {route.route_id: route for route in routes}
    if len(by_id) != len(routes):
        raise ValueError("Route ids must be unique.")

    ineligible: dict[str, IneligibilityReason] = {}
    eligible: list[RouteRiskSummary] = []
    for route in routes:
        reason = _ineligibility(route)
        if reason is None:
            eligible.append(route)
        else:
            ineligible[route.route_id] = reason

    ranked_eligible = sorted(eligible, key=rank_key)
    ranked_ineligible = sorted((by_id[i] for i in ineligible), key=rank_key)
    ranked_ids = [r.route_id for r in ranked_eligible + ranked_ineligible]

    if not ranked_eligible:
        return Recommendation(
            status=RecommendationStatus.NO_SAFE_ROUTE,
            recommended_route_id=None,
            ranked_route_ids=ranked_ids,
            ineligible=ineligible,
            explanation=(
                "No route can be recommended as safe: every option has No Travel conditions "
                "or incomplete forecast coverage. All routes are shown for inspection."
            ),
        )

    best = ranked_eligible[0]
    return Recommendation(
        status=RecommendationStatus.ROUTE_AVAILABLE,
        recommended_route_id=best.route_id,
        ranked_route_ids=ranked_ids,
        ineligible=ineligible,
        explanation=_explain(
            best, ranked_eligible, [(r, ineligible[r.route_id]) for r in ranked_ineligible]
        ),
    )
