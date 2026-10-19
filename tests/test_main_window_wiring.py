"""Headless MainWindow wiring: real controllers and SQLite on tmp_path, VLC disabled.

Covers load -> settings/library, channel activation -> play/last channel/history,
favourite toggle, close -> UI state persisted and restart restore (TEST_AUDIT.md F6).
"""

import logging
from pathlib import Path

import pytest
from PyQt6.QtCore import QEvent

from core.models import Playlist, PlaylistReference, PlaylistSourceType, XtreamCredentials
from core.services.epg_service import EPGService
from core.services.favorites_service import FavoritesService
from core.services.history_service import HistoryService
from core.services.playlist_service import PlaylistService
from core.services.settings_service import SettingsService
from infra.db.epg_repository import EPGRepository
from infra.db.favorites_repository import FavoritesRepository
from infra.db.history_repository import HistoryRepository
from infra.db.playlist_repository import PlaylistRepository
from infra.db.settings_repository import SettingsRepository
from infra.db.sqlite_connection import SQLiteConnection
from infra.playback.vlc_backend import VLCBackend
from ui.controllers.epg_controller import EPGController
from ui.controllers.favorites_controller import FavoritesController
from ui.controllers.history_controller import HistoryController
from ui.controllers.main_controller import MainController
from ui.controllers.playlist_controller import PlaylistController
from ui.controllers.settings_controller import SettingsController
from ui.widgets.player_widget import PlayerWidget
from ui.windows.main_window import MainWindow

M3U = """#EXTM3U
#EXTINF:-1 tvg-id="news.one" group-title="News",News One
http://streams.example/news-one
#EXTINF:-1 tvg-id="sport.one" group-title="Sports",Sport One
http://streams.example/sport-one
"""
NEWS_URL = "http://streams.example/news-one"


class _SyncPool:
    """Stands in for QThreadPool so background loads run inline."""

    def start(self, worker) -> None:
        worker.run()


def _build_window(db_path: Path) -> MainWindow:
    """Mirror app.main.create_window, but on an explicit SQLite file."""
    assert Path.home() / ".simple_iptv" not in db_path.parents
    connection = SQLiteConnection(db_path=db_path)
    playlist_controller = PlaylistController(PlaylistService(PlaylistRepository(connection)))
    playlist_controller._thread_pool = _SyncPool()
    settings_controller = SettingsController(SettingsService(SettingsRepository(connection)))
    return MainWindow(
        MainController(playlist_controller, settings_controller),
        playlist_controller,
        EPGController(EPGService(EPGRepository(connection))),
        settings_controller,
        FavoritesController(FavoritesService(FavoritesRepository(connection))),
        HistoryController(HistoryService(HistoryRepository(connection))),
    )


def _pump_until(qapp, condition, attempts: int = 200) -> None:
    for _ in range(attempts):
        qapp.processEvents()
        if condition():
            return
    pytest.fail("condition not reached while processing Qt events")


def _wait_for_render(qapp, window: MainWindow) -> None:
    _pump_until(
        qapp,
        lambda: (
            window.playlist_controller.get_current_playlist() is not None
            and not window._playlist_render_active
            and window.left_panel.channel_list.channel_model.rowCount() > 0
        ),
    )


def _reload_settings(db_path: Path) -> SettingsService:
    return SettingsService(SettingsRepository(SQLiteConnection(db_path=db_path)))


@pytest.fixture
def playlist_file(tmp_path) -> Path:
    path = tmp_path / "wiring.m3u"
    path.write_text(M3U, encoding="utf-8")
    return path


@pytest.fixture
def file_identity(playlist_file) -> str:
    return PlaylistReference(
        name=playlist_file.name, path=str(playlist_file), source_type=PlaylistSourceType.FILE
    ).source_identity


@pytest.fixture
def db_path(tmp_path) -> Path:
    return tmp_path / "app.sqlite"


@pytest.fixture
def played_urls(monkeypatch) -> list[str]:
    """Disable VLC and record what the player widget is asked to play."""
    monkeypatch.setattr(VLCBackend, "initialize", classmethod(lambda cls: (False, "VLC disabled in tests")))
    played: list[str] = []
    monkeypatch.setattr(PlayerWidget, "play", lambda self, url, **_kwargs: played.append(url))
    return played


@pytest.fixture
def make_window(qapp, played_urls):
    windows: list[MainWindow] = []

    def factory(path: Path) -> MainWindow:
        window = _build_window(path)
        windows.append(window)
        return window

    yield factory
    for window in windows:
        window.close()
        window.left_panel.cancel_channel_population()
        window.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


@pytest.fixture
def loaded_window(qapp, make_window, db_path, playlist_file):
    window = make_window(db_path)
    window.playlist_controller.load_playlist(str(playlist_file))
    _wait_for_render(qapp, window)
    return window


def _activate_first_channel(qapp, window: MainWindow):
    view = window.left_panel.channel_list
    index = view.channel_model.index(0)
    channel = view.channel_model.channel_at(0)
    view.doubleClicked.emit(index)
    qapp.processEvents()
    return channel


def test_loading_playlist_populates_list_settings_and_library(loaded_window, db_path, playlist_file, file_identity):
    window = loaded_window

    assert window.left_panel.channel_list.channel_model.rowCount() == 2
    settings = _reload_settings(db_path).settings
    assert settings.last_playlist_identity == file_identity
    assert settings.last_playlist_source_type == "file"
    assert settings.last_playlist_path == str(playlist_file)
    saved = PlaylistRepository(SQLiteConnection(db_path=db_path)).get_playlist_by_identity(file_identity)
    assert saved is not None
    assert saved.path == str(playlist_file)


def test_activating_channel_logs_name_but_never_stream_url(qapp, make_window, db_path, playlist_file, caplog):
    with caplog.at_level(logging.DEBUG):
        window = make_window(db_path)
        window.playlist_controller.load_playlist(str(playlist_file))
        _wait_for_render(qapp, window)
        channel = _activate_first_channel(qapp, window)

    assert f"Playing channel {channel.name!r}" in caplog.text
    assert "Playlist 'wiring.m3u' loaded: 2 channels" in caplog.text
    assert channel.url not in caplog.text


def test_activating_channel_plays_and_records_last_channel_and_history(
    qapp, loaded_window, db_path, played_urls, file_identity
):
    channel = _activate_first_channel(qapp, loaded_window)

    assert played_urls == [channel.url]
    assert _reload_settings(db_path).settings.last_channel_url == channel.url
    recent = HistoryRepository(SQLiteConnection(db_path=db_path)).get_recent_channels()
    assert [(c.url, c.playlist_path) for c in recent] == [(channel.url, file_identity)]


def test_favorite_button_toggles_current_channel(qapp, loaded_window, db_path):
    window = loaded_window
    channel = _activate_first_channel(qapp, window)
    favorites = FavoritesRepository(SQLiteConnection(db_path=db_path))

    window.right_panel.favorite_button.click()
    qapp.processEvents()
    assert favorites.is_favorite(channel) is True

    window.right_panel.favorite_button.click()
    qapp.processEvents()
    assert favorites.is_favorite(channel) is False


def test_closing_window_persists_ui_state(qapp, loaded_window, db_path):
    window = loaded_window
    window.left_panel.category_combo.setCurrentText("Sports")
    window.left_panel.search_bar.setText("sport")
    window.left_panel.tabs.setCurrentIndex(1)
    qapp.processEvents()

    window.close()

    settings = _reload_settings(db_path).settings
    assert settings.selected_category == "Sports"
    assert settings.search_text == "sport"
    assert settings.active_tab_index == 1
    assert settings.splitter_sizes == tuple(window.splitter.sizes())


def test_closing_window_saves_settings_before_player_shutdown(loaded_window, monkeypatch):
    calls: list[str] = []
    real_save = loaded_window.settings_controller.save_settings

    def spy_save(*args, **kwargs):
        calls.append("save")
        return real_save(*args, **kwargs)

    monkeypatch.setattr(loaded_window.settings_controller, "save_settings", spy_save)
    monkeypatch.setattr(loaded_window.right_panel.player_widget, "shutdown", lambda: calls.append("shutdown"))

    loaded_window.close()

    assert calls == ["save", "shutdown"]


def test_closing_window_cancels_background_loads(loaded_window, monkeypatch):
    cancelled: list[str] = []
    monkeypatch.setattr(loaded_window.playlist_controller, "cancel_loading", lambda: cancelled.append("playlist"))
    monkeypatch.setattr(loaded_window.epg_controller, "cancel_loading", lambda: cancelled.append("epg"))

    loaded_window.close()

    assert sorted(cancelled) == ["epg", "playlist"]


def test_restart_restores_last_playlist_and_channel(
    qapp, make_window, loaded_window, db_path, played_urls, file_identity
):
    channel = _activate_first_channel(qapp, loaded_window)
    loaded_window.close()
    played_urls.clear()

    restarted = make_window(db_path)
    _wait_for_render(qapp, restarted)

    playlist = restarted.playlist_controller.get_current_playlist()
    assert playlist is not None
    assert playlist.source_reference.source_identity == file_identity
    assert played_urls == [channel.url]


XTREAM_PASSWORD = "s3cret-pass"


@pytest.fixture
def xtream_window(qapp, make_window, db_path, monkeypatch):
    """A window whose active playlist is an Xtream source; guide downloads are recorded, not fetched."""
    window = make_window(db_path)
    window.epg_controller._thread_pool = _SyncPool()
    requested: list[str] = []
    monkeypatch.setattr(EPGService, "load_epg_from_url", lambda self, url, **_kwargs: requested.append(url))
    reference = PlaylistReference(
        name="Provider",
        path="",
        source_type=PlaylistSourceType.XTREAM,
        xtream=XtreamCredentials("http://provider.example:8080/", "user", XTREAM_PASSWORD),
    )
    window.playlist_controller.service.set_current_playlist(
        Playlist(name="Provider", source_path=reference.source_identity, source_reference=reference)
    )
    window.requested_epg_urls = requested
    window.xtream_identity = reference.source_identity
    return window


def test_xtream_epg_url_targets_xmltv_endpoint():
    credentials = XtreamCredentials("http://provider.example:8080/player_api.php", " user ", "p&ss word")
    assert credentials.epg_url() == "http://provider.example:8080/xmltv.php?username=user&password=p%26ss+word"


def test_xtream_source_auto_loads_provider_guide_without_storing_password(qapp, xtream_window, db_path):
    window = xtream_window
    window._auto_load_xtream_epg()
    qapp.processEvents()

    assert window.requested_epg_urls == [
        f"http://provider.example:8080/xmltv.php?username=user&password={XTREAM_PASSWORD}"
    ]
    settings = _reload_settings(db_path).settings
    assert settings.last_epg_url == ""
    assert settings.last_epg_path == ""
    assert settings.last_epg_xtream_identity == window.xtream_identity
    assert window.menu_bar.epg_url_input.text() == ""
    with SQLiteConnection(db_path=db_path).get_connection() as conn:
        stored_values = [row[0] for row in conn.execute("SELECT value FROM settings")]
    assert not any(XTREAM_PASSWORD in value for value in stored_values)


def test_xtream_guide_is_not_redownloaded_while_cache_is_fresh(qapp, xtream_window):
    window = xtream_window
    window._auto_load_xtream_epg()
    qapp.processEvents()
    window._auto_load_xtream_epg()
    qapp.processEvents()
    assert len(window.requested_epg_urls) == 1

    window.settings_controller.save_setting("last_epg_loaded_at", "2000-01-01 00:00")
    window._auto_load_xtream_epg()
    qapp.processEvents()
    assert len(window.requested_epg_urls) == 2


def test_manual_guide_url_disables_xtream_auto_load(qapp, xtream_window):
    window = xtream_window
    window.settings_controller.save_setting("epg_url", "http://guide.example/epg.xml")
    window._auto_load_xtream_epg()
    qapp.processEvents()
    assert window.requested_epg_urls == []


def test_refresh_and_empty_guide_field_fall_back_to_xtream_guide(qapp, xtream_window):
    window = xtream_window
    window._refresh_epg()
    qapp.processEvents()
    window.menu_bar.epg_url_input.clear()
    window._load_epg_url()
    qapp.processEvents()
    assert len(window.requested_epg_urls) == 2
    assert all("/xmltv.php?" in url for url in window.requested_epg_urls)
