"""Byte budgets and deadlines for remote downloads and gzip EPG decompression (no network)."""

import gzip
import io
import logging
import tempfile

import pytest
import requests
from _http import FakeResponse

from core import limits
from core.bounded_download import USER_AGENT, read_bounded
from core.errors import DownloadLimitError, NetworkError, ParsingError
from core.models import XtreamCredentials
from core.services.epg_service import EPGService
from core.services.playlist_service import PlaylistService
from infra.db.epg_repository import EPGRepository
from infra.db.sqlite_connection import SQLiteConnection
from infra.providers.xtream_client import XtreamClient

PLAYLIST_URL = "https://example.com/get/list.m3u"
EPG_URL = "https://example.com/guide.xml"
M3U_BODY = b"#EXTM3U\n#EXTINF:-1,One\nhttp://example.com/one\n"
EPG_XML = (
    b'<tv><programme channel="c" start="20260401000000 +0000" '
    b'stop="20260401010000 +0000"><title>X</title></programme></tv>'
)


def _stream_response(body: bytes, *, content_length: str | None = None) -> FakeResponse:
    headers = {} if content_length is None else {"Content-Length": content_length}
    return FakeResponse(body, headers=headers, chunk_size=10)


@pytest.fixture
def temp_dir(tmp_path, monkeypatch):
    directory = tmp_path / "scratch"
    directory.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(directory))
    return directory


def _playlist_service() -> PlaylistService:
    return PlaylistService(object())  # type: ignore[arg-type]


def _epg_service(tmp_path) -> EPGService:
    return EPGService(EPGRepository(SQLiteConnection(db_path=tmp_path / "epg.sqlite")))


def _install_playlist_get(monkeypatch, response):
    calls: list[str] = []

    def fake_get(url, **kwargs):
        assert kwargs.get("stream") is True
        assert kwargs.get("headers") == {"User-Agent": USER_AGENT}
        calls.append(url)
        return response

    monkeypatch.setattr("core.services.playlist_service.requests.get", fake_get)
    return calls


def test_read_bounded_collects_body_and_closes():
    response = _stream_response(b"x" * 25)

    assert read_bounded(response, max_bytes=100, deadline_seconds=10, description="Test") == b"x" * 25
    assert response.closed


def test_read_bounded_writes_to_sink():
    response = _stream_response(b"y" * 25)
    sink = io.BytesIO()

    assert read_bounded(response, max_bytes=100, deadline_seconds=10, description="Test", sink=sink) == b""
    assert sink.getvalue() == b"y" * 25


def test_read_bounded_ignores_malformed_content_length():
    response = _stream_response(b"z" * 5, content_length="not-a-number")

    assert read_bounded(response, max_bytes=100, deadline_seconds=10, description="Test") == b"z" * 5


def test_read_bounded_deadline_uses_monotonic_clock_and_closes(monkeypatch):
    ticks = iter([0.0, 1.0, 50.0, 100.0])
    monkeypatch.setattr("core.bounded_download.time.monotonic", lambda: next(ticks))
    response = _stream_response(b"x" * 100)

    with pytest.raises(NetworkError, match="too long"):
        read_bounded(response, max_bytes=1000, deadline_seconds=10, description="Test")

    assert response.closed


def test_playlist_over_budget_by_content_length_is_not_retried(monkeypatch, temp_dir):
    monkeypatch.setattr(limits, "MAX_PLAYLIST_DOWNLOAD_BYTES", 10)
    response = _stream_response(M3U_BODY, content_length=str(len(M3U_BODY)))
    calls = _install_playlist_get(monkeypatch, response)

    with pytest.raises(NetworkError, match="too large"):
        _playlist_service().load_playlist(PLAYLIST_URL, is_url=True)

    assert len(calls) == 1
    assert response.closed
    assert list(temp_dir.iterdir()) == []


def test_playlist_over_budget_by_streamed_chunks_is_not_retried(monkeypatch, temp_dir):
    monkeypatch.setattr(limits, "MAX_PLAYLIST_DOWNLOAD_BYTES", 20)
    response = _stream_response(M3U_BODY)  # no Content-Length header
    calls = _install_playlist_get(monkeypatch, response)

    with pytest.raises(NetworkError, match="too large"):
        _playlist_service().load_playlist(PLAYLIST_URL, is_url=True)

    assert len(calls) == 1
    assert response.closed


def test_playlist_deadline_exceeded_is_not_retried(monkeypatch, temp_dir):
    monkeypatch.setattr(limits, "PLAYLIST_DOWNLOAD_DEADLINE_SECONDS", -1)
    response = _stream_response(M3U_BODY)
    calls = _install_playlist_get(monkeypatch, response)

    with pytest.raises(NetworkError, match="too long"):
        _playlist_service().load_playlist(PLAYLIST_URL, is_url=True)

    assert len(calls) == 1
    assert response.closed


def test_playlist_mid_stream_error_is_retried_and_mapped(monkeypatch, temp_dir):
    class _Broken(FakeResponse):
        def iter_content(self, chunk_size: int = 1):
            yield b"#EXTM3U\n"
            raise requests.exceptions.ChunkedEncodingError("connection broken")

    calls = _install_playlist_get(monkeypatch, _Broken(b""))

    with pytest.raises(NetworkError) as excinfo:
        _playlist_service().load_playlist(PLAYLIST_URL, is_url=True)

    assert not isinstance(excinfo.value, DownloadLimitError)
    assert len(calls) == 3


class _StatusResponse(FakeResponse):
    def __init__(self, status_code: int):
        super().__init__(b"", status_code=status_code)

    def raise_for_status(self) -> None:
        raise requests.exceptions.HTTPError(f"{self.status_code} Error for url: {PLAYLIST_URL}", response=self)  # type: ignore[arg-type]


def _install_sequence(monkeypatch, responses):
    calls: list[str] = []
    queue = list(responses)

    def fake_get(url, **kwargs):
        calls.append(url)
        return queue.pop(0)

    monkeypatch.setattr("core.services.playlist_service.requests.get", fake_get)
    return calls


def test_playlist_404_is_not_retried(monkeypatch):
    response = _StatusResponse(404)
    calls = _install_sequence(monkeypatch, [response])
    delays: list[float] = []
    monkeypatch.setattr("core.services.playlist_service._sleep", delays.append)

    with pytest.raises(NetworkError, match="Failed to download playlist"):
        _playlist_service()._download_with_retries(PLAYLIST_URL)

    assert len(calls) == 1
    assert delays == []
    assert response.closed


@pytest.mark.parametrize("status", [408, 429, 500, 503])
def test_playlist_transient_http_status_is_retried(monkeypatch, status):
    calls = _install_sequence(monkeypatch, [_StatusResponse(status), _stream_response(M3U_BODY)])

    assert _playlist_service()._download_with_retries(PLAYLIST_URL) == M3U_BODY
    assert len(calls) == 2


def test_playlist_http_error_without_response_is_retried(monkeypatch):
    no_response = FakeResponse(error=requests.exceptions.HTTPError("no response attached"))

    calls = _install_sequence(monkeypatch, [no_response, _stream_response(M3U_BODY)])

    assert _playlist_service()._download_with_retries(PLAYLIST_URL) == M3U_BODY
    assert len(calls) == 2


def test_playlist_cancel_during_backoff_stops_retries_without_error_log(monkeypatch, caplog):
    from concurrent.futures import CancelledError

    from core.models import PlaylistReference

    calls = _install_sequence(monkeypatch, [_StatusResponse(503)] * 3)
    cancelled = {"flag": False}
    monkeypatch.setattr("core.services.playlist_service._sleep", lambda _s: cancelled.update(flag=True))

    with caplog.at_level(logging.DEBUG), pytest.raises(CancelledError):
        _playlist_service()._load_from_url(
            PlaylistReference(name="x", path=PLAYLIST_URL), cancel_callback=lambda: cancelled["flag"]
        )

    assert len(calls) == 1
    assert "Unexpected playlist URL load failure" not in caplog.text


def test_playlist_retry_backoff_is_exponential_and_skips_final_attempt(monkeypatch):
    calls = _install_sequence(monkeypatch, [_StatusResponse(503)] * 3)
    delays: list[float] = []
    monkeypatch.setattr("core.services.playlist_service._sleep", delays.append)

    with pytest.raises(NetworkError):
        _playlist_service()._download_with_retries(PLAYLIST_URL)

    assert len(calls) == 3
    assert delays == [0.5, 1.0]


def test_playlist_retry_does_not_sleep_after_cancellation(monkeypatch):
    from concurrent.futures import CancelledError

    calls = _install_sequence(monkeypatch, [_StatusResponse(503)] * 3)
    delays: list[float] = []
    monkeypatch.setattr("core.services.playlist_service._sleep", delays.append)

    with pytest.raises(CancelledError):
        _playlist_service()._download_with_retries(PLAYLIST_URL, cancel_callback=lambda: True)

    assert len(calls) == 1
    assert delays == []


def test_epg_url_over_budget_raises_network_error_and_removes_temp_file(monkeypatch, tmp_path, temp_dir, caplog):
    monkeypatch.setattr(limits, "MAX_EPG_DOWNLOAD_BYTES", 20)
    response = _stream_response(EPG_XML)
    monkeypatch.setattr("core.services.epg_service.requests.get", lambda url, **kwargs: response)

    with caplog.at_level(logging.DEBUG), pytest.raises(DownloadLimitError, match="too large"):
        _epg_service(tmp_path).load_epg_from_url(EPG_URL)

    assert "Unexpected EPG URL load failure" not in caplog.text
    assert response.closed
    assert list(temp_dir.iterdir()) == []


def test_epg_url_within_budget_loads(monkeypatch, tmp_path, temp_dir):
    response = _stream_response(EPG_XML)
    monkeypatch.setattr("core.services.epg_service.requests.get", lambda url, **kwargs: response)
    service = _epg_service(tmp_path)

    service.load_epg_from_url(EPG_URL)

    assert service.loaded_channels == ["c"]
    assert list(temp_dir.iterdir()) == []


def test_epg_url_download_sends_app_user_agent(monkeypatch, tmp_path, temp_dir):
    # Some Xtream providers answer 403 to the default python-requests User-Agent.
    seen_headers: list[dict] = []

    def fake_get(url, **kwargs):
        seen_headers.append(kwargs.get("headers"))
        return _stream_response(EPG_XML)

    monkeypatch.setattr("core.services.epg_service.requests.get", fake_get)
    _epg_service(tmp_path).load_epg_from_url(EPG_URL)

    assert seen_headers == [{"User-Agent": USER_AGENT}]


def test_xtream_response_over_budget_raises_network_error(monkeypatch):
    monkeypatch.setattr(limits, "MAX_XTREAM_RESPONSE_BYTES", 10)
    client = XtreamClient()
    response = _stream_response(b'{"user_info": {"auth": 1, "status": "Active"}}')
    response.status_code = 200  # type: ignore[attr-defined]
    monkeypatch.setattr(client.session, "get", lambda url, **kwargs: response)
    credentials = XtreamCredentials(server_url="https://provider.example", username="alice", password="secret")

    with pytest.raises(NetworkError, match="too large") as excinfo:
        client.validate_credentials(credentials)

    assert "secret" not in str(excinfo.value)
    assert response.closed


def test_xtream_https_retry_over_budget_surfaces_limit_error(monkeypatch):
    monkeypatch.setattr(limits, "MAX_XTREAM_RESPONSE_BYTES", 10)
    client = XtreamClient()
    big = _stream_response(b'{"user_info": {"auth": 1, "status": "Active"}}')

    def fake_get(url, **kwargs):
        if url.startswith("http://"):
            raise requests.exceptions.ConnectionError("refused")
        return big

    monkeypatch.setattr(client.session, "get", fake_get)
    credentials = XtreamCredentials(server_url="http://provider.example", username="alice", password="secret")

    with pytest.raises(DownloadLimitError, match="too large"):
        client.validate_credentials(credentials)


def _json_response(body: bytes, content_type: str) -> FakeResponse:
    response = _stream_response(body)
    response.headers["Content-Type"] = content_type
    return response


def test_xtream_json_honours_declared_charset(monkeypatch):
    client = XtreamClient()
    # "€" is 0x80 in windows-1252; the latin-1 fallback would decode it as "\x80" instead.
    body = '{"user_info": {"auth": 1, "status": "Active"}, "name": "Café €"}'.encode("cp1252")
    response = _json_response(body, "application/json; charset=windows-1252")
    monkeypatch.setattr(client.session, "get", lambda url, **kwargs: response)
    credentials = XtreamCredentials(server_url="https://provider.example", username="alice", password="secret")

    assert client.validate_credentials(credentials)["name"] == "Café €"


def test_xtream_json_declared_utf8_charset_tolerates_bom(monkeypatch):
    client = XtreamClient()
    body = b"\xef\xbb\xbf" + '{"user_info": {"auth": 1, "status": "Active"}, "name": "Café"}'.encode()
    response = _json_response(body, "application/json; charset=utf-8")
    monkeypatch.setattr(client.session, "get", lambda url, **kwargs: response)
    credentials = XtreamCredentials(server_url="https://provider.example", username="alice", password="secret")

    assert client.validate_credentials(credentials)["name"] == "Café"


def test_xtream_json_utf8_without_charset(monkeypatch):
    client = XtreamClient()
    body = '{"user_info": {"auth": 1, "status": "Active"}, "name": "Café"}'.encode()
    response = _json_response(body, "application/json")
    monkeypatch.setattr(client.session, "get", lambda url, **kwargs: response)
    credentials = XtreamCredentials(server_url="https://provider.example", username="alice", password="secret")

    assert client.validate_credentials(credentials)["name"] == "Café"


def test_xtream_invalid_json_still_raises_parsing_error(monkeypatch):
    client = XtreamClient()
    response = _stream_response(b"<html>not json</html>")
    monkeypatch.setattr(client.session, "get", lambda url, **kwargs: response)
    credentials = XtreamCredentials(server_url="https://provider.example", username="alice", password="secret")

    with pytest.raises(ParsingError, match="invalid JSON"):
        client.validate_credentials(credentials)

    assert response.closed


def test_gzip_bomb_is_rejected_as_parsing_error(monkeypatch, tmp_path):
    monkeypatch.setattr(limits, "MAX_EPG_DECOMPRESSED_BYTES", 1000)
    bomb = tmp_path / "bomb.xml.gz"
    bomb.write_bytes(gzip.compress(b"<tv><!--" + b"a" * 200_000 + b"--></tv>"))
    assert bomb.stat().st_size < 1000

    with pytest.raises(ParsingError) as excinfo:
        _epg_service(tmp_path).load_epg_from_path(str(bomb))

    assert "limit" in str(excinfo.value.__cause__)


def test_normal_gzip_epg_still_loads(tmp_path):
    path = tmp_path / "guide.xml.gz"
    path.write_bytes(gzip.compress(EPG_XML))
    service = _epg_service(tmp_path)

    service.load_epg_from_path(str(path))

    assert service.loaded_channels == ["c"]
