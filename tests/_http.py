"""Shared stand-in for a streamed ``requests`` response."""

import json
from typing import Any


class FakeResponse:
    """Yields ``body`` in ``chunk_size`` pieces (whole body by default); ``error`` is raised by raise_for_status."""

    def __init__(
        self,
        body: bytes = b"",
        *,
        error: Exception | None = None,
        headers: dict[str, str] | None = None,
        chunk_size: int | None = None,
        status_code: int = 200,
    ):
        self.content = body
        self.status_code = status_code
        self.headers = headers or {}
        self._error = error
        self._chunk_size = chunk_size or max(len(body), 1)
        self.closed = False

    def raise_for_status(self) -> None:
        if self._error is not None:
            raise self._error

    def iter_content(self, chunk_size: int = 1):
        for start in range(0, len(self.content), self._chunk_size):
            yield self.content[start : start + self._chunk_size]

    def close(self) -> None:
        self.closed = True


def json_response(payload: Any) -> FakeResponse:
    return FakeResponse(json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
