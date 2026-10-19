"""Restart round trip: persist the active playlist, rebuild everything, restore it.

Kills M1 (identity no longer read back from the DB) and M2 (legacy ``is_url`` flag
inverted) from docs/archive/TEST_AUDIT.md.
"""

import pytest

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


def _raw_setting(db_path, key: str) -> str:
    """Read a stored key directly; SettingsService only exposes typed attributes."""
    return SettingsRepository(SQLiteConnection(db_path=db_path)).get_setting(key, "<missing>")


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
    assert _raw_setting(db_path, "last_playlist_is_url") == "false"


def test_save_active_playlist_url_survives_reload(qapp, tmp_path):
    db_path = tmp_path / "app.sqlite"
    reference = PlaylistReference(name="URL Playlist", path=M3U_URL, source_type=PlaylistSourceType.URL)

    _Stack(db_path).settings_controller.save_active_playlist(reference)

    settings = _reload_settings(db_path)
    assert settings.get_setting("last_playlist_identity") == f"url::{M3U_URL}"
    assert settings.get_setting("last_playlist_source_type") == "url"
    assert _raw_setting(db_path, "last_playlist_is_url") == "true"


def test_save_active_playlist_xtream_survives_reload(qapp, tmp_path):
    db_path = tmp_path / "app.sqlite"
    reference = _xtream_reference()

    _Stack(db_path).settings_controller.save_active_playlist(reference)

    settings = _reload_settings(db_path)
    assert settings.get_setting("last_playlist_identity") == reference.source_identity
    assert settings.get_setting("last_playlist_source_type") == "xtream"
    assert _raw_setting(db_path, "last_playlist_is_url") == "false"


def test_xtream_after_file_clears_legacy_path_keys(qapp, tmp_path):
    db_path = tmp_path / "app.sqlite"
    stack = _Stack(db_path)
    stack.settings_controller.save_active_playlist(_file_reference(tmp_path))
    xtream = _xtream_reference()

    stack.settings_controller.save_active_playlist(xtream)

    settings = _reload_settings(db_path)
    assert settings.get_setting("last_playlist_path") == ""
    assert _raw_setting(db_path, "last_playlist") == ""
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


class _RecordingPlaylistController:
    """Boundary fake: nothing is saved by identity, so MainController uses legacy settings."""

    def __init__(self):
        self.loads: list[tuple[str, bool]] = []

    def get_saved_playlist_by_identity(self, identity):
        return None

    def load_playlist(self, source, is_url=False):
        self.loads.append((source, is_url))


class _DictSettingsController:
    def __init__(self, values):
        self.values = values

    def get_setting(self, key, default=None):
        return self.values.get(key, default)


# (flag, source type, path) -> expected is_url. The flag wins when it is a recognised
# boolean ("true" forces URL, "false" defers to the source type); an unrecognised flag
# falls back to sniffing the path scheme.
_FILE_PATH = "/home/user/list.m3u"
_LEGACY_CASES = [
    ("true", "file", _FILE_PATH, True),
    ("true", "file", M3U_URL, True),
    ("true", "url", _FILE_PATH, True),
    ("true", "url", M3U_URL, True),
    ("false", "file", _FILE_PATH, False),
    ("false", "file", M3U_URL, False),
    ("false", "url", _FILE_PATH, True),
    ("false", "url", M3U_URL, True),
    ("garbage", "file", _FILE_PATH, False),
    ("garbage", "file", M3U_URL, True),
    ("garbage", "url", _FILE_PATH, False),
    ("garbage", "url", M3U_URL, True),
]


@pytest.mark.parametrize(("flag", "source_type", "path", "expected_is_url"), _LEGACY_CASES)
def test_main_controller_legacy_fallback_matrix(flag, source_type, path, expected_is_url):
    playlist_controller = _RecordingPlaylistController()
    settings = _DictSettingsController(
        {
            "last_playlist_identity": "",
            "last_playlist_source_type": source_type,
            "last_playlist_path": path,
            "last_playlist_is_url": flag,
        }
    )

    MainController(playlist_controller, settings).start()

    assert playlist_controller.loads == [(path, expected_is_url)]


def test_main_controller_legacy_fallback_uses_old_last_playlist_key():
    playlist_controller = _RecordingPlaylistController()
    settings = _DictSettingsController({"last_playlist": _FILE_PATH, "last_playlist_is_url": "false"})

    MainController(playlist_controller, settings).start()

    assert playlist_controller.loads == [(_FILE_PATH, False)]


def test_main_controller_does_nothing_without_saved_state():
    playlist_controller = _RecordingPlaylistController()

    MainController(playlist_controller, _DictSettingsController({})).start()

    assert playlist_controller.loads == []
