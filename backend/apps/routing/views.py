"""Thin API views: validate input, call a service, serialize the result."""

from datetime import datetime
from typing import Any

from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import TripAnalysisRecord
from .serializers import (
    PlaceSearchQuerySerializer,
    TripAnalyzeRequestSerializer,
    present_corridor_forecast,
    present_trip_analysis,
)
from .services import providers


class TripAnalyzeView(APIView):
    throttle_scope = "trip_analyze"

    def post(self, request: Request) -> Response:
        serializer = TripAnalyzeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        analysis = providers.build_trip_planner().analyze_trip(serializer.to_trip_request())
        result = present_trip_analysis(analysis)
        record = TripAnalysisRecord.objects.create(request=request.data, result=result)

        return Response(_with_id(record), status=status.HTTP_201_CREATED)


class TripDetailView(APIView):
    def get(self, request: Request, analysis_id: str) -> Response:
        record = get_object_or_404(TripAnalysisRecord, pk=analysis_id)
        return Response(_with_id(record))


class CorridorForecastView(APIView):
    """Hourly corridor risk (0-48 h from departure) for a saved analysis.

    Computed on the first request and stored on the record, so the slider and later re-opens
    never trigger new provider calls.
    """

    throttle_scope = "corridor_forecast"

    def get(self, request: Request, analysis_id: str) -> Response:
        record = get_object_or_404(TripAnalysisRecord, pk=analysis_id)
        if record.corridor is None:
            result = record.result
            forecast = providers.build_corridor_forecaster().forecast(
                routes=[
                    [(lon, lat) for lon, lat in route["geometry"]["coordinates"]]
                    for route in result["routes"]
                ],
                departure_at=datetime.fromisoformat(result["departure_at"]),
                load_weight_lb=result["load_weight_lb"],
            )
            record.corridor = present_corridor_forecast(forecast)
            record.save(update_fields=["corridor"])
        return Response({"analysis_id": str(record.id), **record.corridor})


class PlaceSearchView(APIView):
    throttle_scope = "place_search"

    def get(self, request: Request) -> Response:
        query = PlaceSearchQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        places = providers.build_geocoder().search(
            query.validated_data["q"], limit=query.validated_data["limit"]
        )
        return Response({"results": [{"name": p.name, "lon": p.lon, "lat": p.lat} for p in places]})


def _with_id(record: TripAnalysisRecord) -> dict[str, Any]:
    return {"analysis_id": str(record.id), **record.result}
