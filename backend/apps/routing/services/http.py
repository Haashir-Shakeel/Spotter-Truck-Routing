"""Shared JSON GET with bounded retries for provider clients."""

import logging
import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx

from .errors import (
    ProviderConfigurationError,
    ProviderError,
    ProviderRateLimitedError,
    ProviderResponseError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
AUTH_STATUS = frozenset({401, 403})


def get_json(
    client: httpx.Client,
    url: str,
    *,
    params: Mapping[str, str | int | float],
    provider: str,
    max_retries: int = 2,
    backoff_seconds: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """GET ``url`` and return JSON, retrying timeouts, 429 and 5xx a bounded number of times."""
    last_error: ProviderError | None = None

    for attempt in range(max_retries + 1):
        try:
            response = client.get(url, params=params)
        except httpx.TimeoutException:
            last_error = ProviderUnavailableError(provider, "request timed out")
        except httpx.TransportError:
            last_error = ProviderUnavailableError(provider, "connection failed")
        else:
            status = response.status_code
            if status in AUTH_STATUS:
                raise ProviderConfigurationError(provider, f"credentials rejected (HTTP {status})")
            if status == 429:
                last_error = ProviderRateLimitedError(provider, "rate limit exceeded")
            elif status in RETRYABLE_STATUS:
                last_error = ProviderUnavailableError(provider, f"server error (HTTP {status})")
            elif response.is_error:
                raise ProviderResponseError(provider, f"request rejected (HTTP {status})")
            else:
                try:
                    return response.json()
                except ValueError as exc:
                    raise ProviderResponseError(provider, "response was not valid JSON") from exc

        if attempt < max_retries:
            logger.warning("%s attempt %d failed: %s", provider, attempt + 1, last_error.message)
            sleep(backoff_seconds * 2**attempt)

    assert last_error is not None
    raise last_error
