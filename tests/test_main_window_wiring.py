"""Headless MainWindow wiring: real controllers and SQLite on tmp_path, VLC disabled.

Covers load -> settings/library, channel activation -> play/last channel/history,
favourite toggle, close -> UI state persisted and restart restore (TEST_AUDIT.md F6).
"""

import logging
from pathlib import Path

import pytest
from PyQt6.QtCore import QEvent

from core.models import PlaylistReference, PlaylistSourceType
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
