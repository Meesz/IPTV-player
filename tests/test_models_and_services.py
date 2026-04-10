import gzip
import os
import pathlib
from datetime import datetime, timezone
from types import SimpleNamespace

from requests.exceptions import Timeout

import pytest
from PyQt6.QtWidgets import QApplication, QWidget

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
from ui.controllers.epg_controller import EPGController
from ui.controllers.playlist_controller import PlaylistController
from ui.dialogs.playlist_manager_dialog import PlaylistManagerDialog
from ui.widgets.left_panel import LeftPanel
from ui.widgets.notification import NotificationType, NotificationWidget
from ui.widgets.right_panel import RightPanel
from ui.widgets.player_widget import PlayerWidget


@pytest.fixture(scope="session")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

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
    updated = settings.with_updates(
        theme="light",
        volume=42,
        last_playlist_path="/tmp/list.m3u",
        splitter_sizes=(320, 880),
        active_tab_index=2,
        selected_category="News",
        search_text="sport",
        left_panel_visible=False,
    )
    assert updated.theme == "light"
    assert updated.volume == 42
    assert updated.last_playlist_path == "/tmp/list.m3u"
    assert updated.show_now_playing_in_list is True
    assert updated.splitter_sizes == (320, 880)
    assert updated.active_tab_index == 2
    assert updated.selected_category == "News"
    assert updated.search_text == "sport"
    assert updated.left_panel_visible is False


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


def test_playlist_service_uses_canonical_query_pipeline():
    service = PlaylistService(_DummyPlaylistRepository())  # type: ignore[arg-type]
    playlist = Playlist(
        channels=[
            Channel(name="Alpha News", url="https://example.com/a", group="News"),
            Channel(name="Bravo Sports", url="https://example.com/b", group="Sports"),
            Channel(name="Cinema", url="https://example.com/c", group="Movies"),
        ]
    )

    global_results = service.search_channels(
        "sports",
        playlist=playlist,
        category="News",
        current_category_only=False,
    )
    local_results = service.search_channels(
        "sports",
        playlist=playlist,
        category="News",
        current_category_only=True,
    )
    favorites_first = service.search_channels(
        "",
        playlist=playlist,
        favorite_keys={("https://example.com/c", "")},
        sort_mode="favorites_first",
    )

    assert [channel.name for channel in global_results] == ["Bravo Sports"]
    assert local_results == []
    assert favorites_first[0].name == "Cinema"


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
    assert parsed["news.us"].programs[0].start_time.tzinfo == timezone.utc


def test_epg_parser_supports_namespaces_and_gzip(tmp_path):
    epg_path = pathlib.Path(tmp_path) / "sample.xml.gz"
    payload = """
    <tv xmlns="urn:xmltv">
        <programme channel="news.us" start="20260401000000 +0200" stop="20260401010000 +0200">
            <title>Breaking News</title>
            <desc>Live headlines</desc>
            <category>News</category>
        </programme>
    </tv>
    """
    with gzip.open(epg_path, "wb") as stream:
        stream.write(payload.encode("utf-8"))

    parsed, warnings = EPGParser.parse_with_warnings(str(epg_path))

    assert warnings == []
    assert parsed["news.us"].programs[0].title == "Breaking News"
    assert parsed["news.us"].programs[0].start_time == datetime(
        2026, 3, 31, 22, 0, tzinfo=timezone.utc
    )


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
            start_time=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 1, 11, 0, tzinfo=timezone.utc),
        ),
    )

    current = repository.get_current_program(
        "news.us",
        current_time=datetime(2026, 4, 1, 10, 30, tzinfo=timezone.utc),
    )
    missing = repository.get_current_program(
        "news.us",
        current_time=datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc),
    )

    assert current is not None
    assert current.title == "Breaking News"
    assert missing is None
    assert current.start_time.tzinfo == timezone.utc


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


def test_settings_service_persists_extended_ui_state(tmp_path):
    db_path = tmp_path / "settings-extended.sqlite"
    connection = SQLiteConnection(db_path=db_path)
    settings_repo = SettingsRepository(connection)
    service = SettingsService(settings_repo)

    service.save_setting("splitter_sizes", (320, 960))
    service.save_setting("active_tab_index", 2)
    service.save_setting("selected_category", "News")
    service.save_setting("search_text", "sports")
    service.save_setting("left_panel_visible", False)

    reloaded = SettingsService(settings_repo)
    assert reloaded.get_setting("splitter_sizes") == (320, 960)
    assert reloaded.get_setting("active_tab_index") == 2
    assert reloaded.get_setting("selected_category") == "News"
    assert reloaded.get_setting("search_text") == "sports"
    assert reloaded.get_setting("left_panel_visible") is False

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


def test_m3u_parser_collects_warnings_without_dropping_valid_channels(tmp_path):
    playlist_path = tmp_path / "warnings.m3u"
    playlist_path.write_text(
        "\n".join(
            [
                "#EXTM3U",
                "http://example.com/orphan",
                "#EXTINF:-1 tvg-id='news.us' tvg-chno='not-a-number' tvg-shift='oops' group-title='News',News Channel",
                "http://example.com/stream/news",
            ]
        ),
        encoding="utf-8",
    )

    parsed = M3UParser.parse(str(playlist_path))

    assert len(parsed.channels) == 1
    assert parsed.channels[0].name == "News Channel"
    assert parsed.channels[0].channel_number == 0
    assert parsed.channels[0].time_shift == 0
    assert {warning.code for warning in parsed.parse_warnings} == {
        "orphan_stream_url",
        "invalid_numeric_attribute",
    }


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


def test_right_panel_always_clears_playback_detail():
    chip = SimpleNamespace(
        setText=lambda value: setattr(chip, "text", value),
        setProperty=lambda key, value: setattr(chip, key, value),
        style=lambda: SimpleNamespace(unpolish=lambda _widget: None, polish=lambda _widget: None),
    )
    detail = SimpleNamespace(setText=lambda value: setattr(detail, "text", value))
    fake_panel = SimpleNamespace(
        playback_state_chip=chip,
        playback_detail_label=detail,
    )

    RightPanel.set_playback_state(fake_panel, "playing", "Stream is live")
    RightPanel.set_playback_state(fake_panel, "idle", "")

    assert detail.text == ""


def test_left_panel_renders_custom_channel_rows(qapp):
    panel = LeftPanel()
    channel = Channel(
        name="News Live",
        url="https://example.com/news",
        group="News",
        epg_id="news",
    )
    program = Program(
        title="Morning Briefing",
        start_time=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 4, 1, 11, 0, tzinfo=timezone.utc),
    )

    panel.add_channels(
        [channel],
        current_programs={"news": program},
        favorites={channel.identity_key()},
        current_channel_key=channel.identity_key(),
    )

    item = panel.channel_list.item(0)
    widget = panel.channel_list.itemWidget(item)

    assert item.data(0x0100) == channel
    assert widget is not None
    assert widget.title_label.text() == "News Live"
    assert widget.subtitle_label.text() == "Morning Briefing"
    assert "News" in widget.meta_label.text()


def test_left_panel_loading_state(qapp):
    panel = LeftPanel()

    panel.show_loading_state("channels", "Loading playlist", "Parsing 200 channels")

    _stacked, state = panel._collection_views[panel.channel_list]
    assert state.title_label.text() == "Loading playlist"
    assert state.detail_label.text() == "Parsing 200 channels"


def test_notification_widget_queues_messages_and_repositions(qapp):
    parent = QWidget()
    parent.resize(600, 400)
    notification = NotificationWidget(parent)

    notification.show_message("First", NotificationType.INFO, duration=100)
    first_x = notification.x()
    notification.show_message("Second", NotificationType.SUCCESS, duration=100)

    parent.resize(800, 400)
    qapp.processEvents()
    assert notification.x() != first_x

    notification._advance_queue()
    assert notification.text() == "Second"


def test_playlist_manager_shows_inline_validation_and_test_results(qapp, monkeypatch):
    dialog = PlaylistManagerDialog()
    dialog.set_playlist_validator(lambda ref: (None, "Playlist file not found"))
    dialog._add_item("Broken", "/missing/file.m3u", False)

    assert "Playlist file not found" in dialog.feedback_label.text()

    dialog.set_playlist_validator(lambda ref: (ref, ""))
    dialog.set_playlist_tester(
        lambda ref, **_kwargs: PlaylistReference(
            name=ref.name,
            path=ref.path,
            is_url=ref.is_url,
            channel_count=42,
            last_status="ready",
            last_error="",
        )
    )
    monkeypatch.setattr(dialog._thread_pool, "start", lambda worker: worker.run())

    dialog._add_item("Main", "https://example.com/list.m3u", True)
    dialog.playlist_list.setCurrentRow(0)
    dialog._test_selected_playlist()

    assert "42 channels" in dialog.feedback_label.text()
    assert "42" in dialog.detail_channels.text()
    assert "Verified successfully" in dialog.detail_validation.text()


def test_playlist_controller_ignores_stale_worker_result(monkeypatch):
    service = PlaylistService(_DummyPlaylistRepository())  # type: ignore[arg-type]
    controller = PlaylistController(service)
    loaded: list[str] = []
    controller.playlist_loaded.connect(lambda playlist: loaded.append(playlist.source_path))
    monkeypatch.setattr(controller._thread_pool, "start", lambda worker: None)

    slow_playlist = Playlist(
        name="slow",
        source_path="slow.m3u",
        channels=[Channel(name="slow", url="https://example.com/slow")],
    )
    fast_playlist = Playlist(
        name="fast",
        source_path="fast.m3u",
        channels=[Channel(name="fast", url="https://example.com/fast")],
    )

    controller.load_playlist("slow.m3u")
    controller.load_playlist("fast.m3u")
    controller._on_task_succeeded(1, slow_playlist)
    controller._on_task_succeeded(2, fast_playlist)

    assert loaded == ["fast.m3u"]
    assert service.current_playlist is not None
    assert service.current_playlist.source_path == "fast.m3u"


def test_epg_controller_ignores_stale_worker_result(monkeypatch):
    service = EPGService(_FailingEPGRepository())  # type: ignore[arg-type]
    controller = EPGController(service)
    loaded: list[str] = []
    controller.epg_loaded.connect(lambda: loaded.append(controller.last_loaded_source))
    monkeypatch.setattr(controller._thread_pool, "start", lambda worker: None)

    controller.load_epg_file("slow.xml")
    controller.load_epg_file("fast.xml")
    controller._on_task_succeeded(1, None)
    controller._on_task_succeeded(2, None)

    assert loaded == ["fast.xml"]
    assert controller.last_loaded_source == "fast.xml"


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


def test_main_warns_when_vlc_is_unavailable(monkeypatch):
    calls: dict[str, object] = {}

    class _FakeApplication:
        def __init__(self, _args):
            return None

        def setApplicationName(self, name: str) -> None:
            calls["app_name"] = name

        def exec(self) -> int:
            calls["exec_called"] = True
            return 0

    class _FakeWindow:
        def __init__(self):
            self.right_panel = SimpleNamespace(
                player_widget=SimpleNamespace(
                    vlc_available=False,
                    placeholder=SimpleNamespace(text=lambda: "VLC backend unavailable"),
                )
            )

        def show(self) -> None:
            calls["window_shown"] = True

    dialogs: list[tuple[str, str]] = []

    monkeypatch.setattr(app_main, "QApplication", _FakeApplication)
    monkeypatch.setattr(app_main, "create_window", lambda: _FakeWindow())
    monkeypatch.setattr(
        app_main,
        "_show_critical_dialog",
        lambda title, message: dialogs.append((title, message)),
    )

    assert app_main.main() == 0
    assert ("VLC Unavailable", "Playback will be unavailable until VLC is installed and importable.\n\nVLC backend unavailable") in dialogs
    assert calls["window_shown"] is True
    assert calls["exec_called"] is True
