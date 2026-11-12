"""Uniform API error contract: {"error": {"code", "message", "details"}}."""

import logging
from typing import Any

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class ProviderError(APIException):
    """An upstream routing/geocoding/weather provider failed or returned unusable data."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_code = "PROVIDER_ERROR"
    default_detail = "An external data provider failed."


def _error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
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
