"""Security regression tests: Xtream/EPG credentials must never reach logs.

These deliberately avoid importing PyQt6 so they run even without the Qt
runtime. They guard the invariant stated in the project docs that Xtream
passwords and authenticated source URLs must not be written to the log file or
surfaced in error messages.
"""

import logging

import pytest
import requests

from core.errors import NetworkError, RepositoryError, ValidationError
from core.models import PlaylistReference, PlaylistSourceType, XtreamCredentials
from core.redaction import redact_identity, redact_text, redact_url
from core.services.epg_service import EPGService
from core.services.playlist_service import PlaylistService
from infra.db.playlist_repository import PlaylistRepository
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


# --- M3U URL playlists (PlaylistService) -------------------------------------

_M3U_URL = f"http://host/get.php?username=alice&password={_SECRET}&type=m3u_plus"
_M3U_BODY = b'#EXTM3U\n#EXTINF:-1 tvg-id="a" group-title="News",Channel A\nhttp://stream.example/a.ts\n'
_MASKS = ("***", "%2A%2A%2A")


def _playlist_service() -> PlaylistService:
    return PlaylistService(None, xtream_client=XtreamClient())  # type: ignore[arg-type]


def _raise_timeout(url, timeout=20):
    raise requests.exceptions.Timeout(f"timed out fetching {url}")


def _raise_connection_error(url, timeout=20):
    raise requests.exceptions.ConnectionError(
        f"HTTPConnectionPool(host='host', port=80): Max retries exceeded with url: {url}"
    )


def _raise_http_error(url, timeout=20):
    raise requests.exceptions.HTTPError(f"404 Client Error: Not Found for url: {url}")


class _OkResponse:
    content = _M3U_BODY

    def raise_for_status(self):
        return None


@pytest.mark.parametrize("failure", [_raise_timeout, _raise_connection_error, _raise_http_error])
def test_m3u_url_failure_does_not_leak_password(monkeypatch, caplog, failure):
    monkeypatch.setattr("core.services.playlist_service.requests.get", failure)

    with caplog.at_level(logging.DEBUG), pytest.raises(NetworkError) as excinfo:
        _playlist_service().load_playlist(_M3U_URL, is_url=True)

    assert _SECRET not in caplog.text
    assert _SECRET not in str(excinfo.value)
    assert any(mask in str(excinfo.value) for mask in _MASKS)


def test_m3u_url_success_does_not_leak_password(monkeypatch, caplog):
    monkeypatch.setattr("core.services.playlist_service.requests.get", lambda url, timeout=20: _OkResponse())

    with caplog.at_level(logging.DEBUG):
        playlist = _playlist_service().load_playlist(_M3U_URL, is_url=True)

    assert len(playlist.channels) == 1
    assert _SECRET not in caplog.text


def test_m3u_url_basic_auth_failure_does_not_leak_password(monkeypatch, caplog):
    monkeypatch.setattr("core.services.playlist_service.requests.get", _raise_connection_error)
    url = f"http://alice:{_SECRET}@host/list.m3u"

    with caplog.at_level(logging.DEBUG), pytest.raises(NetworkError) as excinfo:
        _playlist_service().load_playlist(url, is_url=True)

    assert _SECRET not in caplog.text
    assert _SECRET not in str(excinfo.value)
    assert "alice:***@host" in str(excinfo.value)


def test_duplicate_url_validation_error_does_not_leak_password():
    service = _playlist_service()
    reference = PlaylistReference(name="One", path=_M3U_URL, source_type=PlaylistSourceType.URL)
    keys: set[tuple[str, ...]] = set()
    service.validate_playlist_reference(reference, existing_keys=keys)

    with pytest.raises(ValidationError) as excinfo:
        service.validate_playlist_reference(reference, existing_keys=keys)

    assert "Duplicate playlist URL" in str(excinfo.value)
    assert _SECRET not in str(excinfo.value)


# --- redaction helpers --------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected_parts"),
    [
        (f"http://h/p?username=a&password={_SECRET}&type=x", ["username=a", "type=x", "password=%2A%2A%2A"]),
        (f"http://h/p?username=a&password={_SECRET}", ["username=a", "password=%2A%2A%2A"]),
        ("http://h/p?username=a&password=Sec%20ret%21&x=1", ["x=1", "password=%2A%2A%2A"]),
        (f"http://h/p?PASS={_SECRET}", ["PASS=%2A%2A%2A"]),
        (f"http://h/p?pwd={_SECRET}", ["pwd=%2A%2A%2A"]),
        (f"http://alice:{_SECRET}@host/list.m3u", ["alice:***@host/list.m3u"]),
        (f"http://alice:{_SECRET}@host:8080/list.m3u", ["alice:***@host:8080/list.m3u"]),
    ],
)
def test_redact_url_masks_secrets(url, expected_parts):
    redacted = redact_url(url)
    assert _SECRET not in redacted
    assert "Sec%20ret" not in redacted
    for part in expected_parts:
        assert part in redacted


@pytest.mark.parametrize("url", ["http://host/list.m3u", "http://host/p?username=a&type=m3u", "not a url", ""])
def test_redact_url_passes_through_without_secrets(url):
    assert redact_url(url) == url


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (f"bad url: http://h/p?username=a&password={_SECRET}&type=x", "password=***&type=x"),
        (f"bad url: http://h/p?username=a&password={_SECRET}", "password=***"),
        ("with url /p?password=Sec%20ret'", "password=***'"),
        (f"/p?PWD={_SECRET}&x=1", "PWD=***&x=1"),
        (f"/p?Pass={_SECRET}", "Pass=***"),
        (f"refused http://alice:{_SECRET}@host/x", "http://alice:***@host/x"),
        (f"refused http://alice:{_SECRET}@host:8080/x", "http://alice:***@host:8080/x"),
    ],
)
def test_redact_text_masks_secrets(text, expected):
    redacted = redact_text(text)
    assert _SECRET not in redacted
    assert "Sec%20ret" not in redacted
    assert expected in redacted


@pytest.mark.parametrize(
    "url",
    [
        f"http://alice:{_SECRET}@host:80a/list.m3u",
        f"http://alice:{_SECRET}@host:99999/list.m3u",
        f"http://alice:{_SECRET}@host:99999/list.m3u?password={_SECRET}",
    ],
)
def test_redact_url_masks_unparseable_bad_port_urls(url):
    redacted = redact_url(url)
    assert _SECRET not in redacted
    assert "***" in redacted


def test_m3u_url_with_bad_port_does_not_leak_password(monkeypatch, caplog):
    def _fail(url, timeout=20):
        raise requests.exceptions.ConnectionError(f"cannot connect to {url}")

    monkeypatch.setattr("core.services.playlist_service.requests.get", _fail)
    url = f"http://alice:{_SECRET}@host:80a/list.m3u"

    with caplog.at_level(logging.DEBUG), pytest.raises((NetworkError, ValidationError)) as excinfo:
        _playlist_service().load_playlist(url, is_url=True)

    assert _SECRET not in caplog.text
    assert _SECRET not in str(excinfo.value)


def test_passwd_key_is_redacted():
    assert _SECRET not in redact_url(f"http://h/p?passwd={_SECRET}&x=1")
    assert "passwd=***&x=1" in redact_text(f"/p?passwd={_SECRET}&x=1")


def test_redact_identity_masks_url_identities_only():
    masked = redact_identity(f"url::http://alice:{_SECRET}@host/l.m3u?password={_SECRET}")
    assert masked.startswith("url::http://alice:***@host/l.m3u")
    assert _SECRET not in masked
    assert redact_identity("file::/home/user/list.m3u") == "file::/home/user/list.m3u"


def test_repository_error_log_does_not_leak_identity_secret(caplog):
    class _BrokenDb:
        def get_connection(self):
            raise RuntimeError("database unavailable")

    repo = PlaylistRepository(_BrokenDb())  # type: ignore[arg-type]
    identity = f"url::http://h/l.m3u?password={_SECRET}"

    with caplog.at_level(logging.DEBUG), pytest.raises(RepositoryError):
        repo.get_playlist_by_identity(identity)
    with caplog.at_level(logging.DEBUG), pytest.raises(RepositoryError):
        repo.delete_playlist(identity)
    with caplog.at_level(logging.DEBUG), pytest.raises(RepositoryError):
        repo.update_playlist_metadata(identity, channel_count=1, last_loaded_at="", last_status="ok")

    assert "Failed to load playlist" in caplog.text
    assert _SECRET not in caplog.text


def test_epg_unexpected_failure_log_redacts_exception_text(monkeypatch, caplog):
    class _LeakyRepo:
        def save_all(self, _programs_by_channel):
            raise RuntimeError(f"boom at http://h/x?password={_SECRET}")

        def clear(self):
            return None

    class _Resp:
        content = (
            b'<tv><programme channel="c" start="20260401000000 +0000" '
            b'stop="20260401010000 +0000"><title>X</title></programme></tv>'
        )

        def raise_for_status(self):
            return None

        def close(self):
            return None

    service = EPGService(_LeakyRepo())  # type: ignore[arg-type]
    monkeypatch.setattr("core.services.epg_service.requests.get", lambda url, timeout=20: _Resp())

    with caplog.at_level(logging.DEBUG, logger="core.services.epg_service"), pytest.raises(RuntimeError):
        service.load_epg_from_url("http://host/xmltv.php")

    assert _SECRET not in caplog.text


def test_redact_text_passes_through_without_secrets():
    text = "Connection refused for http://host:8080/list.m3u?username=a"
    assert redact_text(text) == text
