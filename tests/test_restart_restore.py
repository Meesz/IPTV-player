"""Restart round trip: persist the active playlist, rebuild everything, restore it.

Kills M1 (identity no longer read back from the DB) from docs/archive/TEST_AUDIT.md.
Restore is identity-only; legacy settings keys are not read on startup.
"""

from core.models import PlaylistReference, PlaylistSourceType, XtreamCredentials
from core.services.playlist_service import PlaylistService
from core.services.settings_service import SettingsService
from infra.db.playlist_repository import PlaylistRepository
from infra.db.settings_repository import SettingsRepository
from infra.db.sqlite_connection import SQLiteConnection
from ui.controllers.main_controller import MainController
from ui.controllers.playlist_controller import PlaylistController
from ui.controllers.settings_controller import SettingsController

M3U_URL = "https://example.com/list.m3u"


class _Stack:
    """One 'process lifetime' of services and controllers on a single SQLite file."""

    def __init__(self, db_path):
        self.connection = SQLiteConnection(db_path=db_path)
        self.playlist_service = PlaylistService(PlaylistRepository(self.connection))
        self.settings_controller = SettingsController(SettingsService(SettingsRepository(self.connection)))
        self.playlist_controller = PlaylistController(self.playlist_service)


def _persist_active_playlist(stack: _Stack, reference: PlaylistReference) -> None:
    """Persist like MainWindow._persist_playlist_state: active-playlist settings + library entry."""
    stack.settings_controller.save_active_playlist(reference)
    stack.playlist_service.save_playlist_reference(reference)


def _restart_and_capture_load(db_path, monkeypatch):
    """Build brand-new objects on the same DB, run MainController.start, return the worker."""
    stack = _Stack(db_path)
    started = []
    monkeypatch.setattr(stack.playlist_controller._thread_pool, "start", started.append)
    MainController(stack.playlist_controller, stack.settings_controller).start()
    assert len(started) == 1
    return started[0]


def _xtream_reference() -> PlaylistReference:
    return PlaylistReference(
        name="Provider",
        source_type=PlaylistSourceType.XTREAM,
        xtream=XtreamCredentials(
            server_url="https://provider.example",
            username="alice",
            password="secret",
            output="ts",
        ),
    )


def test_restart_restores_xtream_source_with_password(qapp, tmp_path, monkeypatch):
    db_path = tmp_path / "app.sqlite"
    reference = _xtream_reference()
    _persist_active_playlist(_Stack(db_path), reference)

    worker = _restart_and_capture_load(db_path, monkeypatch)

    restored = worker.args[0]
    assert isinstance(restored, PlaylistReference)
    assert restored.source_type == PlaylistSourceType.XTREAM
    assert restored.source_identity == reference.source_identity
    assert restored.xtream is not None
    assert restored.xtream.password == "secret"


def test_restart_restores_file_playlist(qapp, tmp_path, monkeypatch):
    playlist_file = tmp_path / "list.m3u"
    playlist_file.write_text("#EXTM3U\n", encoding="utf-8")
    db_path = tmp_path / "app.sqlite"
    reference = PlaylistReference(name="list.m3u", path=str(playlist_file), source_type=PlaylistSourceType.FILE)
    _persist_active_playlist(_Stack(db_path), reference)

    worker = _restart_and_capture_load(db_path, monkeypatch)

    restored = worker.args[0]
    assert isinstance(restored, PlaylistReference)
    assert restored.source_type == PlaylistSourceType.FILE
    assert restored.source_identity == reference.source_identity
    assert restored.name == "list.m3u"


def test_restart_restores_url_playlist(qapp, tmp_path, monkeypatch):
    db_path = tmp_path / "app.sqlite"
    reference = PlaylistReference(name="URL Playlist", path=M3U_URL, source_type=PlaylistSourceType.URL)
    _persist_active_playlist(_Stack(db_path), reference)

    worker = _restart_and_capture_load(db_path, monkeypatch)

    restored = worker.args[0]
    assert isinstance(restored, PlaylistReference)
    assert restored.source_type == PlaylistSourceType.URL
    assert restored.source_identity == f"url::{M3U_URL}"


def _reload_settings(db_path) -> SettingsService:
    return SettingsService(SettingsRepository(SQLiteConnection(db_path=db_path)))


def _file_reference(tmp_path) -> PlaylistReference:
    playlist_file = tmp_path / "list.m3u"
    playlist_file.write_text("#EXTM3U\n", encoding="utf-8")
    return PlaylistReference(name="list.m3u", path=str(playlist_file), source_type=PlaylistSourceType.FILE)


def test_save_active_playlist_file_survives_reload(qapp, tmp_path):
    db_path = tmp_path / "app.sqlite"
    reference = _file_reference(tmp_path)

    _Stack(db_path).settings_controller.save_active_playlist(reference)

    settings = _reload_settings(db_path)
    assert settings.get_setting("last_playlist_identity") == reference.source_identity
    assert settings.get_setting("last_playlist_source_type") == "file"
    assert settings.get_setting("last_playlist_path") == reference.path


def test_save_active_playlist_url_survives_reload(qapp, tmp_path):
    db_path = tmp_path / "app.sqlite"
    reference = PlaylistReference(name="URL Playlist", path=M3U_URL, source_type=PlaylistSourceType.URL)

    _Stack(db_path).settings_controller.save_active_playlist(reference)

    settings = _reload_settings(db_path)
    assert settings.get_setting("last_playlist_identity") == f"url::{M3U_URL}"
    assert settings.get_setting("last_playlist_source_type") == "url"
    assert settings.get_setting("last_playlist_path") == M3U_URL


def test_save_active_playlist_xtream_survives_reload(qapp, tmp_path):
    db_path = tmp_path / "app.sqlite"
    reference = _xtream_reference()

    _Stack(db_path).settings_controller.save_active_playlist(reference)

    settings = _reload_settings(db_path)
    assert settings.get_setting("last_playlist_identity") == reference.source_identity
    assert settings.get_setting("last_playlist_source_type") == "xtream"


def test_xtream_after_file_clears_playlist_path(qapp, tmp_path):
    db_path = tmp_path / "app.sqlite"
    stack = _Stack(db_path)
    stack.settings_controller.save_active_playlist(_file_reference(tmp_path))
    xtream = _xtream_reference()

    stack.settings_controller.save_active_playlist(xtream)

    settings = _reload_settings(db_path)
    assert settings.get_setting("last_playlist_path") == ""
    assert settings.get_setting("last_playlist_identity") == xtream.source_identity


def test_deleted_xtream_entry_does_not_fall_back_to_previous_file(qapp, tmp_path, monkeypatch):
    db_path = tmp_path / "app.sqlite"
    stack = _Stack(db_path)
    stack.settings_controller.save_active_playlist(_file_reference(tmp_path))
    xtream = _xtream_reference()
    _persist_active_playlist(stack, xtream)
    stack.playlist_service.remove_playlist_reference(xtream)

    restarted = _Stack(db_path)
    started = []
    monkeypatch.setattr(restarted.playlist_controller._thread_pool, "start", started.append)
    MainController(restarted.playlist_controller, restarted.settings_controller).start()

    assert started == []


def test_restart_without_saved_state_loads_nothing(qapp, tmp_path, monkeypatch):
    stack = _Stack(tmp_path / "app.sqlite")
    started = []
    monkeypatch.setattr(stack.playlist_controller._thread_pool, "start", started.append)

    MainController(stack.playlist_controller, stack.settings_controller).start()

    assert started == []
