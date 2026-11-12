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


class TripInputError(Exception):
    """The trip request cannot be analyzed as given (maps to HTTP 400)."""

    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class NoRouteFoundError(TripInputError):
    """The routing provider found no drivable route between the two places (HTTP 422)."""

    def __init__(self) -> None:
        super().__init__("NO_ROUTE_FOUND", "No drivable route was found between these places.")
