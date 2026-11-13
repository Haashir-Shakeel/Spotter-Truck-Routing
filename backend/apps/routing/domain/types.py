"""Framework-free value objects shared by the risk, aggregation and recommendation services."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .risk_levels import RiskLevel

# (longitude, latitude) in degrees — GeoJSON order, as returned by routing providers.
Coordinate = tuple[float, float]


@dataclass(frozen=True, slots=True)
class GeocodedPlace:
    name: str
    lon: float
    lat: float


@dataclass(frozen=True, slots=True)
class RouteOption:
    """A provider route normalized to internal units."""

    route_id: str
    coordinates: tuple[Coordinate, ...]
    distance_miles: float
    duration_seconds: float
    # Seconds from departure at each coordinate, when the provider gives per-segment timings.
    cumulative_durations: tuple[float, ...] | None = None
    # Set when the route was requested through a detour waypoint rather than offered by the
    # provider as an alternative (see TripPlannerService._fetch_routes).
    via: Coordinate | None = None


@dataclass(frozen=True, slots=True)
class HourlyForecast:
    """Hourly series for one requested point. Values are None where the provider has no data.

    Precipitation values are the amount that fell during the hour *ending* at ``times[i]``,
    which is an in/hr rate for that hour.
    """

    lon: float
    lat: float
    times: tuple[datetime, ...]  # UTC, hourly, ascending
    wind_mph: tuple[float | None, ...]
    rain_in_per_hour: tuple[float | None, ...]
    snow_in_per_hour: tuple[float | None, ...]


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
