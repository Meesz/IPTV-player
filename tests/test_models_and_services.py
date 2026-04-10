import pathlib

from requests.exceptions import Timeout

import pytest

from core.errors import NetworkError
from core.models import Channel, Playlist, PlaylistReference, Settings
from core.services.playlist_service import PlaylistService
from core.services.settings_service import SettingsService
from infra.db.settings_repository import SettingsRepository
from infra.db.sqlite_connection import SQLiteConnection
from infra.parsers.epg_parser import EPGParser
from infra.parsers.m3u_parser import M3UParser

class _DummyPlaylistRepository:
    def __init__(self):
        self.playlists = []

    def upsert_playlist(self, playlist: PlaylistReference) -> None:
        self.playlists.append(playlist)

    def delete_playlist(self, path: str) -> None:
        self.playlists = [item for item in self.playlists if item.path != path]

    def get_playlists(self):
        return self.playlists

    def import_playlists(self, playlists):
        self.playlists = list(playlists)


def test_settings_round_trip():
    settings = Settings.defaults()
    assert settings.theme == "dark"
    updated = settings.with_updates(theme="light", volume=42, last_playlist_path="/tmp/list.m3u")
    assert updated.theme == "light"
    assert updated.volume == 42
    assert updated.last_playlist_path == "/tmp/list.m3u"


def test_playlist_indexing():
    channels = [
        Channel(name="Alpha", url="https://example.com/a", group="News"),
        Channel(name="Beta", url="https://example.com/b", group="News"),
        Channel(name="Movies", url="https://example.com/m", group="Movies"),
    ]
    playlist = Playlist(channels=channels)

    assert playlist.get_channels_by_category("News") == channels[:2]
    assert playlist.get_channel_by_url("https://example.com/m") == channels[2]
    assert playlist.categories == ["Movies", "News"]


def test_playlist_service_handles_download_failure(tmp_path, monkeypatch):
    repo = _DummyPlaylistRepository()
    service = PlaylistService(repo)  # type: ignore[arg-type]

    def _failing_get(*args, **kwargs):
        raise Timeout("temporary issue")

    monkeypatch.setattr("core.services.playlist_service.requests.get", _failing_get)

    with pytest.raises(NetworkError):
        service._download_with_retries("https://example.com/playlist.m3u")


def test_m3u_parser_reads_channels(tmp_path):
    playlist_path = tmp_path / "sample.m3u"
    playlist_path.write_text(
        "\n".join(
            [
                "#EXTM3U",
                '#EXTINF:-1 tvg-id="news.us" tvg-name="News Channel" group-title="News",News Channel',
                "http://example.com/stream/news",
            ]
        ),
        encoding="utf-8",
    )
    parsed = M3UParser.parse(str(playlist_path))
    assert len(parsed.channels) == 1
    assert parsed.channels[0].name == "News Channel"
    assert parsed.channels[0].group == "News"


def test_epg_parser_reads_programs(tmp_path):
    epg_path = pathlib.Path(tmp_path) / "sample.xml"
    epg_path.write_text(
        """
        <tv>
            <programme channel="news.us" start="20260401000000 +0200" stop="20260401010000 +0200">
                <title>Breaking News</title>
                <desc>Live headlines</desc>
                <category>News</category>
            </programme>
        </tv>
        """,
        encoding="utf-8",
    )

    parsed = EPGParser.parse(str(epg_path))
    assert "news.us" in parsed
    assert len(parsed["news.us"].programs) == 1
    assert parsed["news.us"].programs[0].title == "Breaking News"


def test_settings_service_legacy_key_sync(tmp_path):
    db_path = tmp_path / "settings.sqlite"
    connection = SQLiteConnection(db_path=db_path)
    settings_repo = SettingsRepository(connection)
    service = SettingsService(settings_repo)

    service.save_setting("epg_url", "https://example.com/epg.xml")
    service.save_setting("last_playlist_path", "https://example.com/list.m3u")
    assert service.get_setting("last_epg_url") == "https://example.com/epg.xml"
    assert service.get_setting("last_playlist_path") == "https://example.com/list.m3u"

    service = SettingsService(settings_repo)
    assert service.get_setting("last_epg_url") == "https://example.com/epg.xml"
    assert service.get_setting("last_playlist_path") == "https://example.com/list.m3u"
