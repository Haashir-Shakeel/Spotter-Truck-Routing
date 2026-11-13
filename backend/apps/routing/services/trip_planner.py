"""Explicit orchestration of one trip analysis.

    places -> routes -> checkpoints -> weather at each ETA -> risk -> risk miles -> recommendation

Every step lives in its own pure or provider module; this service only wires them together and
collects warnings. Providers and the clock are injected so the whole flow is testable offline.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

from apps.routing.domain.types import (
    Checkpoint,
    CheckpointRisk,
    Coordinate,
    GeocodedPlace,
    HourlyForecast,
    Recommendation,
    RiskAssessment,
    RouteOption,
    RouteRiskSummary,
    WeatherConditions,
)

from .checkpoints import generate_checkpoints
from .errors import NoRouteFoundError, ProviderError, TripInputError
from .geo import haversine_miles, offset_midpoint
from .geocoding import GeocodingProvider
from .recommendation import recommend_route
from .risk_engine import InvalidWeatherError, assess_conditions
from .route_aggregation import summarize_route_risk
from .routing_provider import RoutingProvider, deduplicate_routes
from .timezones import TimezoneProvider
from .weather_interpolation import conditions_at
from .weather_provider import WeatherProvider

logger = logging.getLogger(__name__)

MAX_ROUTES = 3
ROUTE_LETTERS = ("A", "B", "C")
MIN_TRIP_MILES = 0.5
DEPARTURE_GRACE = timedelta(hours=1)  # allow "now" with a little clock skew
# Mapbox usually offers at most two routes for US trips. To still compare three, we ask for real
# routes forced through a waypoint beside the trip's midpoint (left, right, then further out).
# A detour is kept only if it is a genuinely different road path and not much slower.
VIA_OFFSET_FRACTIONS = (0.15, -0.15, 0.3, -0.3)  # of the straight-line trip distance
VIA_MIN_OFFSET_MILES = 10.0
VIA_MAX_OFFSET_MILES = 80.0
VIA_MAX_DURATION_RATIO = 1.3  # vs the fastest provider route
# Checkpoints whose coordinates match to ~11 m share one weather lookup.
_WEATHER_POINT_DECIMALS = 4


@dataclass(frozen=True, slots=True)
class LocationInput:
    """What the user typed, plus coordinates when they picked a suggestion."""

    name: str
    lon: float | None = None
    lat: float | None = None


@dataclass(frozen=True, slots=True)
class TripRequest:
    origin: LocationInput
    destination: LocationInput
    departure_at: datetime
    load_weight_lb: float
    checkpoint_interval_miles: int


@dataclass(frozen=True, slots=True)
class AnalysisWarning:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class CheckpointResult:
    checkpoint: Checkpoint
    weather: WeatherConditions | None
    assessment: RiskAssessment | None


@dataclass(frozen=True, slots=True)
class RouteAnalysis:
    route: RouteOption
    label: str
    checkpoints: list[CheckpointResult]
    summary: RouteRiskSummary
    arrival_at: datetime
    eta_method: str  # "segment_durations" or "proportional"


@dataclass(frozen=True, slots=True)
class TripAnalysis:
    request: TripRequest
    origin: GeocodedPlace
    destination: GeocodedPlace
    routes: list[RouteAnalysis]
    recommendation: Recommendation
    generated_at: datetime
    warnings: list[AnalysisWarning] = field(default_factory=list)
    # IANA zones for showing times in trip-local time; None when the lookup failed.
    origin_timezone: str | None = None
    destination_timezone: str | None = None
    weather_source: str = "live"  # "demo" when synthetic demo weather was used


def _weather_key(cp: Checkpoint) -> Coordinate:
    return (round(cp.lon, _WEATHER_POINT_DECIMALS), round(cp.lat, _WEATHER_POINT_DECIMALS))


def _floor_hour(value: datetime) -> datetime:
    return value.replace(minute=0, second=0, microsecond=0)


class TripPlannerService:
    def __init__(
        self,
        *,
        geocoder: GeocodingProvider,
        router: RoutingProvider,
        weather: WeatherProvider,
        timezones: TimezoneProvider | None = None,
        weather_for_trip: Callable[[GeocodedPlace, GeocodedPlace, datetime], WeatherProvider]
        | None = None,
        max_departure_days_ahead: int = 14,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._geocoder = geocoder
        self._router = router
        self._weather = weather
        self._timezones = timezones
        # Demo mode: weather built per trip (storms placed along it) instead of the live provider.
        self._weather_for_trip = weather_for_trip
        self._max_ahead = timedelta(days=max_departure_days_ahead)
        self._clock = clock

    def analyze_trip(self, request: TripRequest) -> TripAnalysis:
        now = self._clock()
        self._validate_departure(request.departure_at, now)

        origin = self._resolve(request.origin, "origin")
        destination = self._resolve(request.destination, "destination")
        trip_miles = haversine_miles((origin.lon, origin.lat), (destination.lon, destination.lat))
        if trip_miles < MIN_TRIP_MILES:
            raise TripInputError("SAME_LOCATION", "Origin and destination are the same place.")

        warnings: list[AnalysisWarning] = []
        weather = self._weather
        if self._weather_for_trip is not None:
            weather = self._weather_for_trip(origin, destination, request.departure_at)
            warnings.append(
                AnalysisWarning(
                    "DEMO_WEATHER",
                    "Demo weather: synthetic storms for walkthroughs, not a real forecast. "
                    "Routes are real.",
                )
            )
        origin_tz, destination_tz = self._lookup_timezones(origin, destination)
        routes = self._fetch_routes(origin, destination, warnings)
        checkpoints_by_route = [self._checkpoints(route, request) for route in routes]
        forecasts = self._forecasts_for(weather, [cp for cps in checkpoints_by_route for cp in cps])

        analyses = [
            self._analyze_route(route, checkpoints, forecasts, request.load_weight_lb)
            for route, checkpoints in zip(routes, checkpoints_by_route, strict=True)
        ]
        warnings.extend(_coverage_warnings(analyses))

        return TripAnalysis(
            request=request,
            origin=origin,
            destination=destination,
            routes=analyses,
            recommendation=recommend_route([a.summary for a in analyses]),
            generated_at=now,
            warnings=warnings,
            origin_timezone=origin_tz,
            destination_timezone=destination_tz,
            weather_source="live" if self._weather_for_trip is None else "demo",
        )

    # --- steps --------------------------------------------------------------------------------

    def _validate_departure(self, departure_at: datetime, now: datetime) -> None:
        if departure_at.tzinfo is None or departure_at.utcoffset() is None:
            raise TripInputError("INVALID_DEPARTURE", "Departure time must include a time zone.")
        if departure_at < now - DEPARTURE_GRACE:
            raise TripInputError(
                "DEPARTURE_IN_PAST", "Departure time is in the past; forecasts cover future trips."
            )
        if departure_at > now + self._max_ahead:
            raise TripInputError(
                "DEPARTURE_TOO_FAR",
                f"Departure must be within {self._max_ahead.days} days for forecast coverage.",
                {"max_days_ahead": self._max_ahead.days},
            )

    def _resolve(self, location: LocationInput, role: str) -> GeocodedPlace:
        if location.lon is not None and location.lat is not None:
            return GeocodedPlace(name=location.name, lon=location.lon, lat=location.lat)
        matches = self._geocoder.search(location.name, limit=1)
        if not matches:
            raise TripInputError(
                "LOCATION_NOT_FOUND",
                f"Could not find the {role} '{location.name}'.",
                {"field": role},
            )
        return matches[0]

    def _lookup_timezones(
        self, origin: GeocodedPlace, destination: GeocodedPlace
    ) -> tuple[str | None, str | None]:
        """Display-only: a failed lookup falls back to the viewer's zone, never fails the trip."""
        if self._timezones is None:
            return None, None
        try:
            zones = self._timezones.timezones(
                [(origin.lon, origin.lat), (destination.lon, destination.lat)]
            )
        except ProviderError:
            logger.warning("Time zone lookup failed; times will use the viewer's zone")
            return None, None
        return zones[0], zones[1]

    def _fetch_routes(
        self, origin: GeocodedPlace, destination: GeocodedPlace, warnings: list[AnalysisWarning]
    ) -> list[RouteOption]:
        start, end = (origin.lon, origin.lat), (destination.lon, destination.lat)
        distinct = deduplicate_routes(self._router.get_routes(start, end))[:MAX_ROUTES]
        if not distinct:
            raise NoRouteFoundError()

        offered = len(distinct)
        if self._add_via_routes(start, end, distinct):
            warnings.append(_via_route_warning(offered, len(distinct)))
        if len(distinct) < MAX_ROUTES:
            plural = "s" if len(distinct) != 1 else ""
            warnings.append(
                AnalysisWarning(
                    "FEWER_ROUTES",
                    f"The routing service returned {len(distinct)} distinct route{plural} "
                    f"for this trip, not {MAX_ROUTES}.",
                )
            )
        return [
            replace(route, route_id=letter)
            for route, letter in zip(distinct, ROUTE_LETTERS, strict=False)
        ]

    def _add_via_routes(self, start: Coordinate, end: Coordinate, routes: list[RouteOption]) -> int:
        """Append detour routes in place until there are three; returns how many were added.

        Optional: a failed detour request never fails the analysis.
        """
        straight = haversine_miles(start, end)
        fastest = min(r.duration_seconds for r in routes)
        added = 0
        for fraction in VIA_OFFSET_FRACTIONS:
            if len(routes) >= MAX_ROUTES:
                break
            offset = max(VIA_MIN_OFFSET_MILES, min(VIA_MAX_OFFSET_MILES, abs(fraction) * straight))
            via = offset_midpoint(start, end, offset if fraction > 0 else -offset)
            try:
                candidates = self._router.get_routes(start, end, via=via)
            except ProviderError:
                logger.warning("Detour route request failed; continuing without it")
                continue
            for candidate in candidates[:1]:
                if candidate.duration_seconds > fastest * VIA_MAX_DURATION_RATIO:
                    continue
                if len(deduplicate_routes([*routes, candidate])) > len(routes):
                    routes.append(candidate)
                    added += 1
        return added

    @staticmethod
    def _checkpoints(route: RouteOption, request: TripRequest) -> list[Checkpoint]:
        return generate_checkpoints(
            coordinates=route.coordinates,
            interval_miles=request.checkpoint_interval_miles,
            departure_at=request.departure_at,
            total_duration_seconds=route.duration_seconds,
            total_distance_miles=route.distance_miles,
            cumulative_durations=route.cumulative_durations,
        )

    @staticmethod
    def _forecasts_for(
        weather: WeatherProvider, checkpoints: Sequence[Checkpoint]
    ) -> dict[Coordinate, HourlyForecast]:
        """One batched forecast request covering every distinct checkpoint and arrival hour."""
        points = list(dict.fromkeys(_weather_key(cp) for cp in checkpoints))
        arrivals = [cp.arrival_at for cp in checkpoints]
        start = _floor_hour(min(arrivals))
        end = _floor_hour(max(arrivals)) + timedelta(hours=1)
        forecasts = weather.hourly_forecasts(points, start, end)
        return dict(zip(points, forecasts, strict=True))

    @staticmethod
    def _analyze_route(
        route: RouteOption,
        checkpoints: Sequence[Checkpoint],
        forecasts: dict[Coordinate, HourlyForecast],
        load_weight_lb: float,
    ) -> RouteAnalysis:
        label = f"Route {route.route_id}"
        results: list[CheckpointResult] = []
        for cp in checkpoints:
            conditions = conditions_at(forecasts[_weather_key(cp)], cp.arrival_at)
            assessment = None
            if conditions is not None:
                try:
                    assessment = assess_conditions(conditions, load_weight_lb)
                except InvalidWeatherError:
                    logger.warning("Invalid weather at checkpoint %d of %s", cp.index, label)
                    conditions = None
            results.append(CheckpointResult(cp, conditions, assessment))

        summary = summarize_route_risk(
            route_id=route.route_id,
            label=label,
            checkpoints=[
                CheckpointRisk(r.checkpoint.distance_miles, r.assessment.level)
                if r.assessment
                else CheckpointRisk(r.checkpoint.distance_miles, None)
                for r in results
            ],
            duration_seconds=route.duration_seconds,
        )
        return RouteAnalysis(
            route=route,
            label=label,
            checkpoints=results,
            summary=summary,
            arrival_at=checkpoints[-1].arrival_at,
            eta_method="segment_durations" if route.cumulative_durations else "proportional",
        )


def _via_route_warning(offered: int, total: int) -> AnalysisWarning:
    letters = ROUTE_LETTERS[offered:total]
    if len(letters) == 1:
        added = f"Route {letters[0]} is a real drivable route"
    else:
        added = f"Routes {' and '.join(letters)} are real drivable routes"
    return AnalysisWarning(
        "VIA_ROUTE",
        f"The routing service offered {offered} route{'s' if offered != 1 else ''} for this trip. "
        f"{added} requested through a waypoint beside the trip so more options can be compared.",
    )


def _coverage_warnings(analyses: Sequence[RouteAnalysis]) -> list[AnalysisWarning]:
    return [
        AnalysisWarning(
            "WEATHER_UNAVAILABLE",
            f"{a.label}: forecast unavailable for {a.summary.unavailable_miles:.1f} of "
            f"{a.summary.distance_miles:.1f} miles, so it is not rated as safe.",
        )
        for a in analyses
        if a.summary.unavailable_miles > 0
    ]
