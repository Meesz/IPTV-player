import os
import sys

sys.path.append(os.getcwd())


def test_imports_smoke():
    from core.models import Channel, Playlist, Settings
    from core.services.history_service import HistoryService
    from core.services.playlist_service import PlaylistService
    from core.services.settings_service import SettingsService
    from infra.db.history_repository import HistoryRepository
    from infra.db.sqlite_connection import SQLiteConnection
    from infra.parsers.m3u_parser import M3UParser
    from ui.controllers.history_controller import HistoryController
    from ui.controllers.main_controller import MainController
    from ui.controllers.playlist_controller import PlaylistController

    assert Channel("name", "url")
    assert Playlist()
    assert Settings.defaults()
    assert M3UParser
    assert SQLiteConnection
    assert PlaylistService
    assert HistoryService
    assert MainController
    assert PlaylistController
    assert HistoryController
    assert HistoryRepository
    assert SettingsService
