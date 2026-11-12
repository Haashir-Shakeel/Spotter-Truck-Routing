import pytest

from apps.core.exceptions import api_exception_handler
from apps.routing.services.errors import (
    ProviderConfigurationError,
    ProviderError,
    ProviderRateLimitedError,
    ProviderResponseError,
    ProviderUnavailableError,
)


@pytest.mark.parametrize(
    ("exc", "status", "code"),
    [
        (ProviderUnavailableError("Open-Meteo", "request timed out"), 503, "PROVIDER_UNAVAILABLE"),
        (ProviderRateLimitedError("Open-Meteo", "rate limited"), 503, "PROVIDER_RATE_LIMITED"),
        (ProviderResponseError("Mapbox Directions", "bad"), 502, "PROVIDER_BAD_RESPONSE"),
        (ProviderConfigurationError("Mapbox", "no token"), 503, "PROVIDER_NOT_CONFIGURED"),
    ],
)
def test_provider_errors_use_the_error_contract(exc: ProviderError, status: int, code: str) -> None:
    response = api_exception_handler(exc, {})

    assert response is not None
    assert response.status_code == status
    assert response.data["error"]["code"] == code
    assert response.data["error"]["details"] == {"provider": exc.provider}


def test_configuration_problems_are_not_revealed_to_clients() -> None:
    response = api_exception_handler(ProviderConfigurationError("Mapbox", "token rejected"), {})

    assert response is not None
    assert "token" not in response.data["error"]["message"]
