"""Bounded reading of streamed ``requests`` responses."""

from __future__ import annotations

import time
from typing import Any, Protocol

from core.errors import DownloadLimitError
from core.limits import DOWNLOAD_CHUNK_BYTES

# Some providers reject the default python-requests User-Agent with 403.
USER_AGENT = "SimpleIPTVPlayer/1.0"


class _ByteSink(Protocol):
    def write(self, data: bytes, /) -> Any: ...


def read_bounded(
    response: Any,
    *,
    max_bytes: int,
    deadline_seconds: float,
    description: str,
    sink: _ByteSink | None = None,
) -> bytes:
    """Read a ``stream=True`` response within a byte budget and a wall-clock deadline.

    Returns the body as bytes, or ``b""`` after writing every chunk to ``sink`` when
    one is given. Raises ``DownloadLimitError`` (never containing the URL) when the
    declared or actual size exceeds ``max_bytes`` or the deadline passes. The response
    is always closed.

    The deadline is best-effort: it is only checked between reads. ``iter_content`` can
    block until a full chunk arrives, so a server trickling data may overrun it; each
    individual socket read is still bounded by the request timeout.
    """
    try:
        declared = _declared_length(response)
        if declared is not None and declared > max_bytes:
            raise DownloadLimitError(f"{description} is too large (limit {max_bytes} bytes)")
        deadline = time.monotonic() + deadline_seconds
        total = 0
        chunks: list[bytes] = []
        for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_BYTES):
            if time.monotonic() > deadline:
                raise DownloadLimitError(
                    f"{description} took too long to download (limit {deadline_seconds:g} seconds)"
                )
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise DownloadLimitError(f"{description} is too large (limit {max_bytes} bytes)")
            if sink is not None:
                sink.write(chunk)
            else:
                chunks.append(chunk)
        return b"".join(chunks)
    finally:
        response.close()


def _declared_length(response: Any) -> int | None:
    headers = getattr(response, "headers", None) or {}
    value = headers.get("Content-Length")
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None
