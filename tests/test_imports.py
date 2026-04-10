import sys
import os
sys.path.append(os.getcwd())


def test_imports_smoke():
    from core.models import Channel, Playlist, Settings
    from core.services.playlist_service import PlaylistService
    from infra.db.sqlite_connection import SQLiteConnection
    from infra.parsers.m3u_parser import M3UParser
    from ui.controllers.main_controller import MainController
    from ui.controllers.playlist_controller import PlaylistController
    from core.services.settings_service import SettingsService

    assert Channel("name", "url")
    assert Playlist()
    assert Settings.defaults()
    assert M3UParser
    assert SQLiteConnection
    assert PlaylistService
    assert MainController
    assert PlaylistController
    assert SettingsService
