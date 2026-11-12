"""Failures talking to external routing, geocoding and weather providers.

These are plain exceptions so the services stay framework-free; the API layer maps them to
HTTP responses. Messages never include request URLs, because URLs can carry access tokens.
"""


class ProviderError(Exception):
    code = "PROVIDER_ERROR"

    def __init__(self, provider: str, message: str) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider = provider
        self.message = message


class ProviderConfigurationError(ProviderError):
    """Missing or rejected credentials."""

    code = "PROVIDER_NOT_CONFIGURED"


class ProviderUnavailableError(ProviderError):
    """Timeout, connection failure or 5xx after retries."""

    code = "PROVIDER_UNAVAILABLE"


class ProviderRateLimitedError(ProviderError):
    code = "PROVIDER_RATE_LIMITED"


class ProviderResponseError(ProviderError):
    """The provider answered, but with an error or data we cannot use."""

    code = "PROVIDER_BAD_RESPONSE"
