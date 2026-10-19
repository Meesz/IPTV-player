"""M3U URL loading (success, retries, temp-file cleanup) and channel ordering.

Kills M6 (download retries reduced to one attempt) and M7 (default sort reversed).
"""

import tempfile
from concurrent.futures import CancelledError

import pytest
import requests

from core.errors import NetworkError, ParsingError
from core.models import Channel, Playlist
from core.services.playlist_service import PlaylistService

PLAYLIST_URL = "https://example.com/get/list.m3u"
M3U_BODY = (
    b"#EXTM3U\n"
    b'#EXTINF:-1 tvg-id="news.one" group-title="News",News One\n'
    b"http://example.com/stream/one\n"
    b'#EXTINF:-1 group-title="Sports",Sports Two\n'
    b"http://example.com/stream/two\n"
)


class _NoRepository:
    """URL loading and querying never touch the repository."""


class _Response:
    def __init__(
        self,
        content: bytes = b"",
        error: Exception | None = None,
        headers: dict[str, str] | None = None,
        chunk_size: int | None = None,
    ):
        self.content = content
        self._error = error
        self.headers = headers or {}
        self._chunk_size = chunk_size or max(len(content), 1)
        self.closed = False

    def raise_for_status(self) -> None:
        if self._error is not None:
            raise self._error

    def iter_content(self, chunk_size: int = 1):
        for start in range(0, len(self.content), self._chunk_size):
            yield self.content[start : start + self._chunk_size]

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def service() -> PlaylistService:
    return PlaylistService(_NoRepository())  # type: ignore[arg-type]


@pytest.fixture
def temp_dir(tmp_path, monkeypatch):
    """Route tempfile output into an empty directory so leftovers are detectable."""
    directory = tmp_path / "scratch"
    directory.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(directory))
    return directory


def _install_get(monkeypatch, responses):
    """Replace requests.get with a scripted sequence; returns the recorded calls."""
    calls: list[str] = []
    queue = list(responses)

    def fake_get(url, **kwargs):
        calls.append(url)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr("core.services.playlist_service.requests.get", fake_get)
    return calls


def test_load_url_playlist_parses_channels_tags_source_and_removes_temp_file(service, temp_dir, monkeypatch):
    calls = _install_get(monkeypatch, [_Response(M3U_BODY)])

    playlist = service.load_playlist(PLAYLIST_URL, is_url=True)

    assert calls == [PLAYLIST_URL]
    assert [channel.name for channel in playlist.channels] == ["News One", "Sports Two"]
    assert playlist.source_path == f"url::{PLAYLIST_URL}"
    assert {channel.playlist_path for channel in playlist.channels} == {f"url::{PLAYLIST_URL}"}
    assert service.current_playlist is playlist
    assert list(temp_dir.iterdir()) == []


def test_load_url_playlist_removes_temp_file_when_parsing_is_cancelled(service, temp_dir, monkeypatch):
    _install_get(monkeypatch, [_Response(M3U_BODY)])
    states = iter([False, True])  # not cancelled before download, cancelled after parsing

    # The service currently re-wraps the cancellation as ParsingError; either is fine here.
    with pytest.raises((CancelledError, ParsingError)):
        service.load_playlist(PLAYLIST_URL, is_url=True, cancel_callback=lambda: next(states, True))

    assert list(temp_dir.iterdir()) == []


def test_download_failure_attempts_three_times_then_raises(service, temp_dir, monkeypatch):
    calls = _install_get(monkeypatch, [requests.ConnectionError("down")] * 3)

    with pytest.raises(NetworkError):
        service.load_playlist(PLAYLIST_URL, is_url=True)

    assert len(calls) == 3
    assert list(temp_dir.iterdir()) == []


def test_download_http_error_attempts_three_times(service, temp_dir, monkeypatch):
    failing = _Response(error=requests.HTTPError("503"))
    calls = _install_get(monkeypatch, [failing, failing, failing])

    with pytest.raises(NetworkError):
        service.load_playlist(PLAYLIST_URL, is_url=True)

    assert len(calls) == 3
    assert failing.closed


def test_transient_failure_then_success_returns_content(service, temp_dir, monkeypatch):
    calls = _install_get(monkeypatch, [requests.Timeout("slow"), _Response(M3U_BODY)])

    playlist = service.load_playlist(PLAYLIST_URL, is_url=True)

    assert len(calls) == 2
    assert [channel.name for channel in playlist.channels] == ["News One", "Sports Two"]
    assert list(temp_dir.iterdir()) == []


# Mixed case, mixed groups; within each group the channel-number order disagrees
# with the name order, so dropping channel_number from the group sort would fail.
def _sort_fixture() -> tuple[Playlist, PlaylistService]:
    playlist = Playlist(
        channels=[
            Channel(name="bravo", url="http://x/bravo", group="News", channel_number=2),
            Channel(name="Alpha", url="http://x/alpha", group="news", channel_number=3),
            Channel(name="delta", url="http://x/delta", group="Movies", channel_number=5),
            Channel(name="Charlie", url="http://x/charlie", group="movies", channel_number=7),
        ]
    )
    return playlist, PlaylistService(_NoRepository())  # type: ignore[arg-type]


FAVORITES = {("http://x/bravo", ""), ("http://x/delta", "")}


@pytest.mark.parametrize(
    ("sort_mode", "expected"),
    [
        ("name_asc", ["Alpha", "bravo", "Charlie", "delta"]),
        ("name_desc", ["delta", "Charlie", "bravo", "Alpha"]),
        # group (case-insensitive), then channel number, then name
        ("group", ["delta", "Charlie", "bravo", "Alpha"]),
        # favourites first, then group, then name
        ("favorites_first", ["delta", "bravo", "Charlie", "Alpha"]),
        # unknown modes fall back to the default ascending name order
        ("no_such_mode", ["Alpha", "bravo", "Charlie", "delta"]),
    ],
)
def test_sort_modes_produce_full_expected_order(sort_mode, expected):
    playlist, service = _sort_fixture()

    results = service.search_channels("", playlist=playlist, sort_mode=sort_mode, favorite_keys=FAVORITES)

    assert [channel.name for channel in results] == expected


def test_default_sort_is_ascending_by_name_when_mode_is_omitted():
    playlist, service = _sort_fixture()

    results = service.search_channels("", playlist=playlist)

    assert [channel.name for channel in results] == ["Alpha", "bravo", "Charlie", "delta"]
