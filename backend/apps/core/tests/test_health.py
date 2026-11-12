from django.urls import reverse
from rest_framework.test import APIClient


def test_health_returns_ok() -> None:
    response = APIClient().get(reverse("health"))

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unknown_api_route_returns_404() -> None:
    response = APIClient().get("/api/v1/does-not-exist/")

    assert response.status_code == 404
