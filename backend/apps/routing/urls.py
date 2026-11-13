from django.urls import path

from .views import CorridorForecastView, PlaceSearchView, TripAnalyzeView, TripDetailView

urlpatterns = [
    path("trips/analyze/", TripAnalyzeView.as_view(), name="trip-analyze"),
    path("trips/<uuid:analysis_id>/", TripDetailView.as_view(), name="trip-detail"),
    path(
        "trips/<uuid:analysis_id>/corridor-forecast/",
        CorridorForecastView.as_view(),
        name="trip-corridor-forecast",
    ),
    path("places/", PlaceSearchView.as_view(), name="place-search"),
]
