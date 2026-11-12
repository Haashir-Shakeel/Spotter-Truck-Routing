import httpx
import pytest

from apps.routing.services.errors import (
    ProviderConfigurationError,
    ProviderRateLimitedError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from apps.routing.services.http import get_json

URL = "https://provider.test/data"


def no_sleep(_: float) -> None:
    pass


def call(client: httpx.Client, max_retries: int = 2):
    return get_json(
        client,
        URL,
        params={"access_token": "secret"},
        provider="Test",
        max_retries=max_retries,
        sleep=no_sleep,
    )


def test_returns_json(mock_client) -> None:
    client, _ = mock_client(lambda r: httpx.Response(200, json={"ok": True}))
    assert call(client) == {"ok": True}


def test_retries_server_errors_then_succeeds(mock_client) -> None:
    responses = iter([httpx.Response(503), httpx.Response(502), httpx.Response(200, json=[1])])
    client, transport = mock_client(lambda r: next(responses))

    assert call(client) == [1]
    assert len(transport.requests) == 3


def test_gives_up_after_bounded_retries(mock_client) -> None:
    client, transport = mock_client(lambda r: httpx.Response(500))

    with pytest.raises(ProviderUnavailableError):
        call(client, max_retries=2)
    assert len(transport.requests) == 3


def test_rate_limit_is_reported_after_retries(mock_client) -> None:
    client, _ = mock_client(lambda r: httpx.Response(429))
    with pytest.raises(ProviderRateLimitedError):
        call(client)


def test_timeout_is_unavailable(mock_client) -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client, _ = mock_client(timeout)
    with pytest.raises(ProviderUnavailableError):
        call(client)


@pytest.mark.parametrize("status", [401, 403])
def test_auth_failure_is_not_retried(mock_client, status: int) -> None:
    client, transport = mock_client(lambda r: httpx.Response(status))

    with pytest.raises(ProviderConfigurationError):
        call(client)
    assert len(transport.requests) == 1


def test_client_error_is_not_retried(mock_client) -> None:
    client, transport = mock_client(lambda r: httpx.Response(422))

    with pytest.raises(ProviderResponseError):
        call(client)
    assert len(transport.requests) == 1


def test_invalid_json_is_rejected(mock_client) -> None:
    client, _ = mock_client(lambda r: httpx.Response(200, text="<html>"))
    with pytest.raises(ProviderResponseError):
        call(client)


def test_error_messages_never_contain_the_token(mock_client) -> None:
    client, _ = mock_client(lambda r: httpx.Response(500))
    with pytest.raises(ProviderUnavailableError) as excinfo:
        call(client)
    assert "secret" not in str(excinfo.value)
