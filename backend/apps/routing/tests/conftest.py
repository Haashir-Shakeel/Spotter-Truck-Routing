from collections.abc import Callable

import httpx
import pytest

from .helpers import RecordingTransport

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def mock_client() -> Callable[[Handler], tuple[httpx.Client, RecordingTransport]]:
    """Build an httpx client whose responses come from ``handler`` (no network)."""

    def build(handler: Handler) -> tuple[httpx.Client, RecordingTransport]:
        transport = RecordingTransport(handler)
        return httpx.Client(transport=transport), transport

    return build
