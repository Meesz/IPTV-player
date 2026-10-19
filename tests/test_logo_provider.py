"""ChannelLogoProvider cache keying, LRU bound and request timeout (fakes only, no network)."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QUrl
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtNetwork import QNetworkReply

from ui.widgets import left_panel
from ui.widgets.left_panel import ChannelLogoProvider


class FakeReply:
    def __init__(self, url: str, payload: bytes = b"", error=QNetworkReply.NetworkError.NoError):
        self._url = url
        self._payload = payload
        self._error = error
        self.deleted = False

    def url(self) -> QUrl:
        return QUrl(self._url)

    def error(self):
        return self._error

    def readAll(self) -> QByteArray:
        return QByteArray(self._payload)

    def deleteLater(self) -> None:
        self.deleted = True


def _png_bytes() -> bytes:
    pixmap = QPixmap(8, 8)
    pixmap.fill(QColor("red"))
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert pixmap.save(buffer, "PNG")
    return bytes(data.data())


@pytest.fixture
def provider(qapp, monkeypatch):
    provider = ChannelLogoProvider()
    provider.requests = []

    def fake_get(request):
        reply = FakeReply(request.url().toString())
        provider.requests.append((request, reply))
        return reply

    monkeypatch.setattr(provider._manager, "get", fake_get)
    yield provider
    provider.deleteLater()


def test_reply_with_changed_url_caches_under_requested_key_and_replaces_fallback(qapp, provider):
    requested = "http://logos.example/a"
    fallback = provider.request_logo(requested, "A")
    emitted: list[str] = []
    provider.logo_loaded.connect(lambda source, _pixmap: emitted.append(source))
    reply = FakeReply("http://cdn.example/redirected/a.png", _png_bytes())
    # Swap the request's own reply for one that reports a different final URL.
    provider._inflight.clear()
    provider._inflight[reply] = requested

    provider._on_reply_finished(reply)

    assert emitted == [requested]
    assert provider._cache[requested] is not fallback
    assert "http://cdn.example/redirected/a.png" not in provider._cache
    assert provider.request_logo(requested, "A") is provider._cache[requested]
    assert provider._inflight == {}
    assert reply.deleted


def test_failed_reply_keeps_fallback_and_clears_inflight(qapp, provider):
    requested = "http://logos.example/broken"
    fallback = provider.request_logo(requested, "B")
    reply = provider.requests[0][1]
    failed = FakeReply(reply.url().toString(), error=QNetworkReply.NetworkError.TimeoutError)
    provider._inflight.clear()
    provider._inflight[failed] = requested

    provider._on_reply_finished(failed)

    assert provider._cache[requested] is fallback
    assert provider._inflight == {}


def test_http_request_sets_transfer_timeout_and_is_deduplicated(qapp, provider):
    provider.request_logo("http://logos.example/a", "A")
    provider.request_logo("http://logos.example/a", "A")

    assert len(provider.requests) == 1
    request = provider.requests[0][0]
    assert request.transferTimeout() == left_panel._LOGO_TRANSFER_TIMEOUT_MS > 0


def test_cache_evicts_least_recently_used_entry_beyond_the_bound(qapp, provider, monkeypatch):
    monkeypatch.setattr(left_panel, "_LOGO_CACHE_MAX_ENTRIES", 3)
    for name in ("a", "b", "c"):
        provider.request_logo(f"missing/{name}.png", name)
    provider.request_logo("missing/a.png", "a")  # touch: "b" is now the oldest

    provider.request_logo("missing/d.png", "d")

    assert list(provider._cache) == ["missing/c.png", "missing/a.png", "missing/d.png"]


def test_theme_change_clears_cache(qapp, provider):
    provider.request_logo("missing/a.png", "a")
    provider.set_theme_mode("light")
    assert len(provider._cache) == 0
