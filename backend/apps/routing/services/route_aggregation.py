"""Turn discrete checkpoint risks into risk miles along a route.

Each stretch between two consecutive checkpoints takes the higher of its two endpoint risks
(conservative). If either endpoint has no forecast, the stretch counts as unavailable miles,
never as Low. Average risk is the mile-weighted ordinal score over the assessed miles.
"""

from collections.abc import Sequence
from itertools import pairwise

from apps.routing.domain.risk_levels import RiskLevel
from apps.routing.domain.types import CheckpointRisk, RouteRiskSummary


def summarize_route_risk(
    *,
    route_id: str,
    checkpoints: Sequence[CheckpointRisk],
    duration_seconds: float,
    label: str | None = None,
) -> RouteRiskSummary:
    if len(checkpoints) < 2:
        raise ValueError("A route needs at least two checkpoints (origin and destination).")

    miles_by_level = dict.fromkeys(RiskLevel, 0.0)
    unavailable_miles = 0.0

    for start, end in pairwise(checkpoints):
        segment_miles = end.distance_miles - start.distance_miles
        if segment_miles < 0:
            raise ValueError("Checkpoints must be ordered by distance along the route.")
        if start.risk is None or end.risk is None:
            unavailable_miles += segment_miles
        else:
            miles_by_level[max(start.risk, end.risk)] += segment_miles

    assessed_miles = sum(miles_by_level.values())
    weighted = sum(level * miles for level, miles in miles_by_level.items())
    known_risks = [cp.risk for cp in checkpoints if cp.risk is not None]

    return RouteRiskSummary(
        route_id=route_id,
        label=label or route_id,
        distance_miles=checkpoints[-1].distance_miles - checkpoints[0].distance_miles,
        duration_seconds=duration_seconds,
        miles_by_level=miles_by_level,
        unavailable_miles=unavailable_miles,
        average_risk=weighted / assessed_miles if assessed_miles > 0 else 0.0,
        max_risk=max(known_risks) if known_risks else None,
    )
