import pathlib
from datetime import datetime
from types import SimpleNamespace

from requests.exceptions import Timeout

import pytest

import app.main as app_main
from core.errors import NetworkError, RepositoryError, ValidationError
from core.models import Channel, Playlist, PlaylistReference, Program, Settings
from core.services.epg_service import EPGService
from core.services.history_service import HistoryService
from core.services.playlist_service import PlaylistService
from core.services.settings_service import SettingsService
from infra.db.epg_repository import EPGRepository
from infra.db.favorites_repository import FavoritesRepository
from infra.db.history_repository import HistoryRepository
from infra.db.playlist_repository import PlaylistRepository
from infra.db.settings_repository import SettingsRepository
from infra.db.sqlite_connection import SQLiteConnection
from infra.parsers.epg_parser import EPGParser
from infra.parsers.m3u_parser import M3UParser
from ui.widgets.player_widget import PlayerWidget

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


class _FailingEPGRepository:
    def save_all(self, _programs_by_channel):
        raise RepositoryError("persist failed")

    def clear(self) -> None:
        return None

    def get_current_program(self, _channel_id, current_time=None):
        return None

    def get_upcoming_programs(self, _channel_id, limit=5):
        return []


def test_settings_round_trip():
    settings = Settings.defaults()
    assert settings.theme == "dark"
    updated = settings.with_updates(theme="light", volume=42, last_playlist_path="/tmp/list.m3u")
    assert updated.theme == "light"
    assert updated.volume == 42
    assert updated.last_playlist_path == "/tmp/list.m3u"
    assert updated.show_now_playing_in_list is True


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


def test_channel_identity_is_source_aware():
    first = Channel(name="News", url="https://example.com/stream", playlist_path="/tmp/a.m3u")
    second = Channel(name="News", url="https://example.com/stream", playlist_path="/tmp/b.m3u")

    assert first != second
    assert len({first, second}) == 2


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


def test_playlist_service_assigns_channel_source_path(tmp_path):
    playlist_path = tmp_path / "sample.m3u"
    playlist_path.write_text(
        "\n".join(
            [
                "#EXTM3U",
                '#EXTINF:-1 tvg-id="news.us" group-title="News",News Channel',
                "http://example.com/stream/news",
            ]
        ),
        encoding="utf-8",
    )
    service = PlaylistService(_DummyPlaylistRepository())  # type: ignore[arg-type]

    playlist = service.load_playlist(str(playlist_path))

    assert playlist.channels[0].playlist_path == str(playlist_path.resolve())


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


def test_epg_service_keeps_persistence_errors_distinct(tmp_path):
    epg_path = pathlib.Path(tmp_path) / "sample.xml"
    epg_path.write_text(
        """
        <tv>
            <programme channel="news.us" start="20260401000000 +0200" stop="20260401010000 +0200">
                <title>Breaking News</title>
            </programme>
        </tv>
        """,
        encoding="utf-8",
    )
    service = EPGService(_FailingEPGRepository())  # type: ignore[arg-type]

    with pytest.raises(RepositoryError):
        service.load_epg_from_path(str(epg_path))

    assert service.loaded_channels == []


def test_epg_repository_uses_supplied_current_time(tmp_path):
    connection = SQLiteConnection(db_path=tmp_path / "epg.sqlite")
    repository = EPGRepository(connection)
    repository.save_program(
        "news.us",
        Program(
            title="Breaking News",
            start_time=datetime(2026, 4, 1, 10, 0),
            end_time=datetime(2026, 4, 1, 11, 0),
        ),
    )

    current = repository.get_current_program(
        "news.us",
        current_time=datetime(2026, 4, 1, 10, 30),
    )
    missing = repository.get_current_program(
        "news.us",
        current_time=datetime(2026, 4, 1, 12, 0),
    )

    assert current is not None
    assert current.title == "Breaking News"
    assert missing is None


def test_settings_service_legacy_key_sync(tmp_path):
    db_path = tmp_path / "settings.sqlite"
    connection = SQLiteConnection(db_path=db_path)
    settings_repo = SettingsRepository(connection)
    service = SettingsService(settings_repo)

    service.save_setting("epg_url", "https://example.com/epg.xml")
    service.save_setting("last_playlist_path", "https://example.com/list.m3u")
    service.save_setting("play_on_single_click", True)
    assert service.get_setting("last_epg_url") == "https://example.com/epg.xml"
    assert service.get_setting("last_playlist_path") == "https://example.com/list.m3u"
    assert service.get_setting("play_on_single_click") is True

    service = SettingsService(settings_repo)
    assert service.get_setting("last_epg_url") == "https://example.com/epg.xml"
    assert service.get_setting("last_playlist_path") == "https://example.com/list.m3u"
    assert service.get_setting("play_on_single_click") is True


def test_recent_history_round_trip(tmp_path):
    connection = SQLiteConnection(db_path=tmp_path / "history.sqlite")
    repository = HistoryRepository(connection)
    service = HistoryService(repository)

    channel = Channel(
        name="News",
        url="https://example.com/news",
        group="News",
        epg_id="news.epg",
    )
    service.record_channel(channel, "https://example.com/playlist.m3u")

    recent = service.get_recent_channels(limit=5)
    assert len(recent) == 1
    assert recent[0].playlist_path == "https://example.com/playlist.m3u"
    assert recent[0].url == channel.url
    assert recent[0].last_played_at is not None


def test_favorites_repository_is_source_aware(tmp_path):
    connection = SQLiteConnection(db_path=tmp_path / "favorites.sqlite")
    repository = FavoritesRepository(connection)

    first = Channel(
        name="News",
        url="https://example.com/news",
        playlist_path="/tmp/a.m3u",
    )
    second = Channel(
        name="News",
        url="https://example.com/news",
        playlist_path="/tmp/b.m3u",
    )

    repository.add_favorite(first)
    repository.add_favorite(second)

    assert repository.is_favorite(first) is True
    assert repository.is_favorite(second) is True
    assert len(repository.get_favorites()) == 2

    repository.remove_favorite(first)

    assert repository.is_favorite(first) is False
    assert repository.is_favorite(second) is True


def test_playlist_metadata_round_trip(tmp_path):
    connection = SQLiteConnection(db_path=tmp_path / "playlist.sqlite")
    repository = PlaylistRepository(connection)

    reference = PlaylistReference(
        name="Main",
        path="/tmp/main.m3u",
        is_url=False,
        channel_count=120,
        last_loaded_at="2026-04-10 12:00",
        last_status="ready",
    )
    repository.upsert_playlist(reference)

    saved = repository.get_playlist("/tmp/main.m3u")
    assert saved is not None
    assert saved.channel_count == 120
    assert saved.last_status == "ready"


def test_playlist_service_rejects_duplicate_references(tmp_path):
    playlist_path = tmp_path / "sample.m3u"
    playlist_path.write_text("#EXTM3U\n", encoding="utf-8")
    connection = SQLiteConnection(db_path=tmp_path / "playlist-duplicates.sqlite")
    repository = PlaylistRepository(connection)
    service = PlaylistService(repository)
    reference = PlaylistReference(name="Main", path=str(playlist_path), is_url=False)

    with pytest.raises(ValidationError):
        service.import_playlists([reference, reference])


def test_playlist_service_blocks_removing_active_playlist(tmp_path):
    playlist_path = tmp_path / "sample.m3u"
    playlist_path.write_text("#EXTM3U\n", encoding="utf-8")
    connection = SQLiteConnection(db_path=tmp_path / "playlist-active.sqlite")
    repository = PlaylistRepository(connection)
    service = PlaylistService(repository)
    reference = PlaylistReference(name="Main", path=str(playlist_path), is_url=False)
    service.save_playlist_reference(reference)

    with pytest.raises(ValidationError):
        service.import_playlists([], active_playlist_path=str(playlist_path))


def test_playlist_repository_import_preserves_metadata(tmp_path):
    playlist_path = tmp_path / "sample.m3u"
    playlist_path.write_text("#EXTM3U\n", encoding="utf-8")
    connection = SQLiteConnection(db_path=tmp_path / "playlist-import.sqlite")
    repository = PlaylistRepository(connection)
    service = PlaylistService(repository)

    reference = PlaylistReference(
        name="Main",
        path=str(playlist_path),
        is_url=False,
        channel_count=120,
        last_loaded_at="2026-04-10 12:00",
        last_status="ready",
        last_error="",
    )

    service.import_playlists([reference])
    saved = service.get_saved_playlist(str(playlist_path))

    assert saved is not None
    assert saved.channel_count == 120
    assert saved.last_loaded_at == "2026-04-10 12:00"
    assert saved.last_status == "ready"


def test_player_retry_flow_stops_at_cap_and_resets_on_success():
    placeholder = SimpleNamespace(
        text="",
        visible=False,
        setText=lambda value: setattr(placeholder, "text", value),
        show=lambda: setattr(placeholder, "visible", True),
        hide=lambda: setattr(placeholder, "visible", False),
    )
    status_overlay = SimpleNamespace(hide=lambda: None)
    timer = SimpleNamespace(
        starts=[],
        start=lambda value: timer.starts.append(value),
        stop=lambda: None,
    )
    state: dict[str, tuple[str, str] | tuple[str, int]] = {}
    fake_widget = SimpleNamespace(
        placeholder=placeholder,
        status_overlay=status_overlay,
        reconnect_timer=timer,
        reconnect_attempts=0,
        max_reconnect_attempts=2,
        current_url="https://example.com/stream",
        player=object(),
        play_calls=[],
        _show_status=lambda message, duration=2000: state.__setitem__(
            "status",
            (message, duration),
        ),
        _set_state=lambda current, detail="": state.__setitem__(
            "playback",
            (current, detail),
        ),
        play=lambda url, is_retry=False: fake_widget.play_calls.append((url, is_retry)),
    )

    PlayerWidget._handle_playback_error(fake_widget, "boom")
    PlayerWidget._handle_playback_error(fake_widget, "boom")
    PlayerWidget._handle_playback_error(fake_widget, "boom")

    assert fake_widget.reconnect_attempts == 2
    assert timer.starts == [2000, 4000]
    assert state["playback"] == ("error", "boom")

    fake_widget.reconnect_attempts = 2
    PlayerWidget._on_media_playing(fake_widget)
    PlayerWidget._reconnect(fake_widget)

    assert fake_widget.reconnect_attempts == 0
    assert fake_widget.play_calls == [("https://example.com/stream", True)]


def test_main_reports_startup_errors(monkeypatch):
    calls: dict[str, object] = {}

    class _FakeApplication:
        def __init__(self, _args):
            return None

        def setApplicationName(self, name: str) -> None:
            calls["app_name"] = name

        def exec(self) -> int:
            calls["exec_called"] = True
            return 0

    def _failing_create_window():
        raise RuntimeError("database unavailable")

    def _critical(_parent, title: str, message: str) -> None:
        calls["dialog"] = (title, message)

    monkeypatch.setattr(app_main, "QApplication", _FakeApplication)
    monkeypatch.setattr(app_main, "create_window", _failing_create_window)
    monkeypatch.setattr(app_main.QMessageBox, "critical", _critical)

    assert app_main.main() == 1
    assert calls["app_name"] == "Simple IPTV Player"
    assert calls["dialog"] == (
        "Startup Error",
        "Failed to start Simple IPTV Player.\n\ndatabase unavailable",
    )
    assert "exec_called" not in calls
