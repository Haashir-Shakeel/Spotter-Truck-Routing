"""Framework-free value objects shared by the risk, aggregation and recommendation services."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .risk_levels import RiskLevel

# (longitude, latitude) in degrees — GeoJSON order, as returned by routing providers.
Coordinate = tuple[float, float]


@dataclass(frozen=True, slots=True)
class Checkpoint:
    """A weather sampling point placed by road distance, with the truck's estimated arrival."""

    index: int
    lon: float
    lat: float
    distance_miles: float
    elapsed_seconds: float
    arrival_at: datetime  # always UTC


@dataclass(frozen=True, slots=True)
class WeatherConditions:
    """Weather at one place and time, already normalized to the units of the risk table."""

    wind_mph: float
    rain_in_per_hour: float
    snow_in_per_hour: float


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """Overall risk plus the per-condition breakdown shown in checkpoint details."""

    level: RiskLevel
    wind: RiskLevel
    rain: RiskLevel
    snow: RiskLevel
    load_override: str | None = None


@dataclass(frozen=True, slots=True)
class CheckpointRisk:
    """A sampled point on a route. ``risk`` is None when weather was unavailable."""

    distance_miles: float
    risk: RiskLevel | None


@dataclass(frozen=True, slots=True)
class RouteRiskSummary:
    route_id: str
    label: str
    distance_miles: float
    duration_seconds: float
    miles_by_level: dict[RiskLevel, float]
    unavailable_miles: float
    average_risk: float
    max_risk: RiskLevel | None

    @property
    def severe_miles(self) -> float:
        return self.miles_by_level[RiskLevel.SEVERE]

    @property
    def high_miles(self) -> float:
        return self.miles_by_level[RiskLevel.HIGH]

    @property
    def no_travel_miles(self) -> float:
        return self.miles_by_level[RiskLevel.NO_TRAVEL]

    @property
    def is_complete(self) -> bool:
        return self.unavailable_miles == 0


class RecommendationStatus(StrEnum):
    ROUTE_AVAILABLE = "route_available"
    NO_SAFE_ROUTE = "no_safe_route"


class IneligibilityReason(StrEnum):
    NO_TRAVEL = "no_travel"
    INCOMPLETE_FORECAST = "incomplete_forecast"


@dataclass(frozen=True, slots=True)
class Recommendation:
    status: RecommendationStatus
    recommended_route_id: str | None
    ranked_route_ids: list[str]
    ineligible: dict[str, IneligibilityReason] = field(default_factory=dict)
    explanation: str = ""
