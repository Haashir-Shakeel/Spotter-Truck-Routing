"""Uniform API error contract: {"error": {"code", "message", "details"}}."""

import logging
from typing import Any

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.routing.services.errors import (
    ProviderConfigurationError,
    ProviderError,
    ProviderResponseError,
)

logger = logging.getLogger(__name__)


def _error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def _provider_error_response(exc: ProviderError) -> Response:
    logger.warning("Provider failure: %s", exc)
    if isinstance(exc, ProviderConfigurationError):
        # Do not tell public clients that our credentials are missing or rejected.
        message = "An external data service is not available right now."
    else:
        message = f"The {exc.provider} service failed: {exc.message}."
    http_status = (
        status.HTTP_502_BAD_GATEWAY
        if isinstance(exc, ProviderResponseError)
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return Response(_error_body(exc.code, message, {"provider": exc.provider}), status=http_status)


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, ProviderError):
        return _provider_error_response(exc)

    response = exception_handler(exc, context)

    if response is None:
        logger.exception("Unhandled API error", exc_info=exc)
        return Response(
            _error_body("INTERNAL_ERROR", "An unexpected error occurred."),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, ValidationError):
        response.data = _error_body("VALIDATION_ERROR", "Invalid request.", exc.detail)
    elif isinstance(exc, APIException):
        codes = exc.get_codes()
        code = codes if isinstance(codes, str) else exc.default_code
        response.data = _error_body(str(code).upper(), str(exc.detail))

    return response
