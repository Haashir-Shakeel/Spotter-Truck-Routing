"""Request validation (DRF serializers) and response presentation for trip analysis."""

from datetime import datetime
from typing import Any

from django.utils.dateparse import parse_datetime
from rest_framework import serializers

from apps.routing.domain.risk_levels import RiskLevel
from apps.routing.services.checkpoints import ALLOWED_INTERVALS_MILES
from apps.routing.services.corridor_forecast import CorridorForecast
from apps.routing.services.geo import simplify_polyline
from apps.routing.services.trip_planner import (
    CheckpointResult,
    LocationInput,
    RouteAnalysis,
    TripAnalysis,
    TripRequest,
)

MAX_LOAD_LB = 150_000
_GEOMETRY_DECIMALS = 5  # ~1 m, keeps responses small
# Display geometry is simplified to ~16 m; that is invisible on the map and cuts thousands of
# vertices per route. Checkpoints and distances always come from the full provider geometry.
DISPLAY_TOLERANCE_MILES = 0.01


class OffsetAwareDateTimeField(serializers.Field):
    """ISO 8601 datetime that must carry a UTC offset, so DST and time zones are unambiguous."""

    default_error_messages = {
        "invalid": "Use ISO 8601, e.g. 2026-11-13T08:00:00-06:00.",
        "naive": "Include a UTC offset or Z, e.g. 2026-11-13T08:00:00-06:00.",
    }

    def to_internal_value(self, data: Any) -> datetime:
        parsed = parse_datetime(data) if isinstance(data, str) else None
        if parsed is None:
            self.fail("invalid")
        if parsed.tzinfo is None:
            self.fail("naive")
        return parsed

    def to_representation(self, value: datetime) -> str:
        return value.isoformat()


class LocationInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, trim_whitespace=True)
    lon = serializers.FloatField(required=False, min_value=-180, max_value=180)
    lat = serializers.FloatField(required=False, min_value=-90, max_value=90)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if ("lon" in attrs) != ("lat" in attrs):
            raise serializers.ValidationError("Provide both lon and lat, or neither.")
        return attrs


class TripAnalyzeRequestSerializer(serializers.Serializer):
    origin = LocationInputSerializer()
    destination = LocationInputSerializer()
    departure_at = OffsetAwareDateTimeField()
    load_weight_lb = serializers.FloatField(min_value=1, max_value=MAX_LOAD_LB)
    checkpoint_interval_miles = serializers.ChoiceField(choices=ALLOWED_INTERVALS_MILES)

    def to_trip_request(self) -> TripRequest:
        data = self.validated_data
        return TripRequest(
            origin=LocationInput(**data["origin"]),
            destination=LocationInput(**data["destination"]),
            departure_at=data["departure_at"],
            load_weight_lb=data["load_weight_lb"],
            checkpoint_interval_miles=int(data["checkpoint_interval_miles"]),
        )


class PlaceSearchQuerySerializer(serializers.Serializer):
    q = serializers.CharField(max_length=200, trim_whitespace=True)
    limit = serializers.IntegerField(required=False, default=5, min_value=1, max_value=10)


# --- presentation -----------------------------------------------------------------------------


def _risk_name(level: RiskLevel | None) -> str | None:
    return level.name if level is not None else None


def _checkpoint(result: CheckpointResult) -> dict[str, Any]:
    cp, weather, assessment = result.checkpoint, result.weather, result.assessment
    return {
        "index": cp.index,
        "lon": round(cp.lon, _GEOMETRY_DECIMALS),
        "lat": round(cp.lat, _GEOMETRY_DECIMALS),
        "distance_miles": round(cp.distance_miles, 2),
        "elapsed_seconds": round(cp.elapsed_seconds),
        "arrival_at": cp.arrival_at.isoformat(),
        "weather": None
        if weather is None
        else {
            "wind_mph": round(weather.wind_mph, 1),
            "rain_in_per_hour": round(weather.rain_in_per_hour, 3),
            "snow_in_per_hour": round(weather.snow_in_per_hour, 3),
        },
        "risk": _risk_name(assessment.level) if assessment else None,
        "risk_detail": None
        if assessment is None
        else {
            "wind": assessment.wind.name,
            "rain": assessment.rain.name,
            "snow": assessment.snow.name,
        },
        "load_override": assessment.load_override if assessment else None,
    }


def _route(analysis: RouteAnalysis) -> dict[str, Any]:
    summary = analysis.summary
    miles = summary.miles_by_level
    return {
        "id": analysis.route.route_id,
        "label": analysis.label,
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [round(lon, _GEOMETRY_DECIMALS), round(lat, _GEOMETRY_DECIMALS)]
                for lon, lat in simplify_polyline(
                    analysis.route.coordinates, DISPLAY_TOLERANCE_MILES
                )
            ],
        },
        "distance_miles": round(analysis.route.distance_miles, 2),
        "duration_seconds": round(analysis.route.duration_seconds),
        "arrival_at": analysis.arrival_at.isoformat(),
        "eta_method": analysis.eta_method,
        "risk_summary": {
            "low_miles": round(miles[RiskLevel.LOW], 2),
            "moderate_miles": round(miles[RiskLevel.MODERATE], 2),
            "high_miles": round(miles[RiskLevel.HIGH], 2),
            "severe_miles": round(miles[RiskLevel.SEVERE], 2),
            "no_travel_miles": round(miles[RiskLevel.NO_TRAVEL], 2),
            "unavailable_miles": round(summary.unavailable_miles, 2),
            "average_risk": round(summary.average_risk, 4),
            "max_risk": _risk_name(summary.max_risk),
            "complete": summary.is_complete,
        },
        "checkpoints": [_checkpoint(r) for r in analysis.checkpoints],
    }


def present_trip_analysis(analysis: TripAnalysis) -> dict[str, Any]:
    """JSON-ready dict for the API response (``analysis_id`` is added by the view)."""
    request, rec = analysis.request, analysis.recommendation
    return {
        "status": "complete",
        "generated_at": analysis.generated_at.isoformat(),
        "departure_at": request.departure_at.isoformat(),
        "load_weight_lb": request.load_weight_lb,
        "checkpoint_interval_miles": request.checkpoint_interval_miles,
        "origin": {
            "name": analysis.origin.name,
            "lon": analysis.origin.lon,
            "lat": analysis.origin.lat,
        },
        "destination": {
            "name": analysis.destination.name,
            "lon": analysis.destination.lon,
            "lat": analysis.destination.lat,
        },
        "recommendation": {
            "status": rec.status.value,
            "recommended_route_id": rec.recommended_route_id,
            "ranked_route_ids": rec.ranked_route_ids,
            "ineligible": {route_id: reason.value for route_id, reason in rec.ineligible.items()},
            "explanation": rec.explanation,
        },
        "routes": [_route(r) for r in analysis.routes],
        "warnings": [{"code": w.code, "message": w.message} for w in analysis.warnings],
    }


def present_corridor_forecast(forecast: CorridorForecast) -> dict[str, Any]:
    """Compact series for the slider: ``risk[hour][point]`` is a RiskLevel value or null.

    Levels are integers (index into ``levels``) so 49 hours x a few hundred points stay small.
    """
    grid = forecast.grid
    return {
        "start_at": forecast.start_at.isoformat(),
        "hour_count": forecast.hour_count,
        "spacing_miles": grid.spacing_miles,
        "buffer_miles": grid.buffer_miles,
        "levels": [level.name for level in RiskLevel],
        "points": [[lon, lat] for lon, lat in grid.points],
        "risk": [
            [None if level is None else int(level) for level in hour] for hour in forecast.risk
        ],
    }
