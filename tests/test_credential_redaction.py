"""Security regression tests: Xtream/EPG credentials must never reach logs.

These deliberately avoid importing PyQt6 so they run even without the Qt
runtime. They guard the invariant stated in the project docs that Xtream
passwords and authenticated source URLs must not be written to the log file or
surfaced in error messages.
"""

import logging

import pytest
import requests

from core.errors import NetworkError, RepositoryError
from core.models import XtreamCredentials
from core.services.epg_service import EPGService
from infra.providers.xtream_client import XtreamClient

_SECRET = "SuperSecret123"


def _make_credentials() -> XtreamCredentials:
    return XtreamCredentials(
        server_url="https://provider.example",
        username="alice",
        password=_SECRET,
        output="ts",
    )


def test_xtream_redacts_password_on_http_error(monkeypatch, caplog):
    client = XtreamClient(timeout=5)
    credentials = _make_credentials()

    def _fake_get(url, timeout):
        response = requests.Response()
        response.status_code = 401
        response.url = url
        response.reason = "Unauthorized"
        raise requests.exceptions.HTTPError(
            f"401 Client Error: Unauthorized for url: {url}",
            response=response,
        )

    monkeypatch.setattr(client.session, "get", _fake_get)

    with caplog.at_level(logging.DEBUG, logger="infra.providers.xtream_client"), pytest.raises(NetworkError):
        client.validate_credentials(credentials)

    assert _SECRET not in caplog.text
    assert "password=***" in caplog.text


def test_xtream_redacts_password_on_connection_error(monkeypatch, caplog):
    client = XtreamClient(timeout=5)
    credentials = _make_credentials()

    def _fake_get(url, timeout):
        # urllib3/requests embed the full request path+query in this message.
        raise requests.exceptions.ConnectionError(
            f"HTTPSConnectionPool(host='provider.example', port=443): "
            f"Max retries exceeded with url: /player_api.php?username=alice&password={_SECRET}"
        )

    monkeypatch.setattr(client.session, "get", _fake_get)

    with caplog.at_level(logging.DEBUG, logger="infra.providers.xtream_client"), pytest.raises(NetworkError):
        client.validate_credentials(credentials)

    assert _SECRET not in caplog.text


def test_redact_secrets_handles_urlencoded_and_trailing_password():
    masked_mid = XtreamClient._redact_secrets("scheme://h/p?username=a&password=Sec%20ret&action=x")
    masked_end = XtreamClient._redact_secrets("for url: https://h/p?username=a&password=Sec%20ret")
    assert "Sec%20ret" not in masked_mid and "password=***" in masked_mid
    assert "Sec%20ret" not in masked_end and "password=***" in masked_end


def test_epg_url_failure_redacts_password_in_log(monkeypatch, caplog):
    """A non-network failure after a successful download must not log the URL password."""

    class _FailingRepo:
        def save_all(self, _programs_by_channel):
            raise RepositoryError("database is locked")

        def clear(self):
            return None

    service = EPGService(_FailingRepo())  # type: ignore[arg-type]

    class _Resp:
        content = (
            b'<tv><programme channel="c" start="20260401000000 +0000" '
            b'stop="20260401010000 +0000"><title>X</title></programme></tv>'
        )

        def raise_for_status(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr("core.services.epg_service.requests.get", lambda url, timeout=20: _Resp())
    url = f"http://host/xmltv.php?username=alice&password={_SECRET}&type=m3u_plus"

    with caplog.at_level(logging.DEBUG, logger="core.services.epg_service"), pytest.raises(RepositoryError):
        service.load_epg_from_url(url)

    assert _SECRET not in caplog.text


def test_epg_url_network_error_message_is_redacted(monkeypatch):
    """The NetworkError surfaced to the UI must not contain the password."""
    service = EPGService(_NoopRepo())  # type: ignore[arg-type]

    def _timeout(url, timeout=20):
        raise requests.exceptions.Timeout("slow")

    monkeypatch.setattr("core.services.epg_service.requests.get", _timeout)
    url = f"http://host/xmltv.php?username=alice&password={_SECRET}"

    with pytest.raises(NetworkError) as excinfo:
        service.load_epg_from_url(url)

    message = str(excinfo.value)
    assert _SECRET not in message
    # urlencode renders the mask as %2A%2A%2A; either form proves redaction.
    assert "password=%2A%2A%2A" in message or "password=***" in message


def test_redact_url_preserves_host_and_path():
    redacted = EPGService._redact_url(f"http://host/xmltv.php?username=alice&password={_SECRET}")
    assert redacted.startswith("http://host/xmltv.php")
    assert "username=alice" in redacted
    assert _SECRET not in redacted


def test_redact_url_masks_basic_auth_userinfo():
    # Password in userinfo, with a query string.
    with_query = EPGService._redact_url(f"http://alice:{_SECRET}@host:8080/epg.xml?type=m3u")
    assert _SECRET not in with_query
    assert "alice:***@host:8080" in with_query
    assert "type=m3u" in with_query

    # Password in userinfo, no query string (previously returned verbatim).
    no_query = EPGService._redact_url(f"http://alice:{_SECRET}@host/epg.xml")
    assert _SECRET not in no_query
    assert "alice:***@host" in no_query


def test_epg_url_failure_redacts_basic_auth_in_log(monkeypatch, caplog):
    """A userinfo password must not reach the log on a download failure."""
    service = EPGService(_NoopRepo())  # type: ignore[arg-type]

    def _conn_error(url, timeout=20):
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr("core.services.epg_service.requests.get", _conn_error)
    url = f"http://alice:{_SECRET}@host/epg.xml"

    with caplog.at_level(logging.DEBUG, logger="core.services.epg_service"), pytest.raises(NetworkError) as excinfo:
        service.load_epg_from_url(url)

    assert _SECRET not in caplog.text
    assert _SECRET not in str(excinfo.value)


class _NoopRepo:
    def save_all(self, _programs_by_channel):
        return None

    def clear(self):
        return None
