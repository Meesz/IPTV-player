"""Migration-robustness tests for the embedded SQLite schema upgrade.

Qt-free so they run without the PyQt6 runtime. They guard the fix that stopped
a legacy `playlists` migration from aborting startup (and locking the user out
of the whole database) when two legacy paths collapse to one source identity.
"""

import logging
import os
import sqlite3
import stat
from pathlib import Path

import pytest

from core.models import PlaylistReference, PlaylistSourceType
from infra.db.playlist_repository import PlaylistRepository
from infra.db.sqlite_connection import SQLiteConnection


def _make_legacy_db(path) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            path TEXT NOT NULL,
            is_url BOOLEAN NOT NULL DEFAULT 0
        );
        """
    )
    return conn


def test_migration_tolerates_colliding_legacy_paths(tmp_path):
    """Two legacy file rows that resolve to one identity must not crash startup."""
    db_path = tmp_path / "legacy-collision.sqlite"
    base = tmp_path / "a.m3u"
    conn = _make_legacy_db(db_path)
    conn.execute("INSERT INTO playlists (name, path, is_url) VALUES ('A', ?, 0)", (str(base),))
    conn.execute(
        "INSERT INTO playlists (name, path, is_url) VALUES ('A dup', ?, 0)",
        (str(tmp_path / "sub" / ".." / "a.m3u"),),
    )
    conn.commit()
    conn.close()

    # Previously raised sqlite3.IntegrityError out of __init__.
    migrated = SQLiteConnection(db_path=db_path)
    playlists = PlaylistRepository(migrated).get_playlists()

    assert len(playlists) == 1
    assert playlists[0].source_type == PlaylistSourceType.FILE


def test_migration_uses_runtime_identity_semantics(tmp_path):
    """Migrated file identity must match what the running app computes (abspath)."""
    db_path = tmp_path / "legacy-identity.sqlite"
    base = tmp_path / "channels.m3u"
    conn = _make_legacy_db(db_path)
    # Store a non-normalized path with a redundant '.' segment.
    conn.execute(
        "INSERT INTO playlists (name, path, is_url) VALUES ('Main', ?, 0)",
        (str(tmp_path / "." / "channels.m3u"),),
    )
    conn.commit()
    conn.close()

    migrated = SQLiteConnection(db_path=db_path)
    repository = PlaylistRepository(migrated)

    runtime_identity = PlaylistReference(
        name="Main",
        path=str(base),
        source_type=PlaylistSourceType.FILE,
    ).source_identity

    assert repository.get_playlist_by_identity(runtime_identity) is not None


def test_migration_preserves_legacy_url_rows(tmp_path):
    """URL rows still migrate verbatim (no path resolution)."""
    db_path = tmp_path / "legacy-url.sqlite"
    conn = _make_legacy_db(db_path)
    conn.execute("INSERT INTO playlists (name, path, is_url) VALUES ('Remote', 'https://example.com/list.m3u', 1)")
    conn.commit()
    conn.close()

    migrated = SQLiteConnection(db_path=db_path)
    playlists = PlaylistRepository(migrated).get_playlists()

    assert len(playlists) == 1
    assert playlists[0].source_type == PlaylistSourceType.URL
    assert playlists[0].path == "https://example.com/list.m3u"


posix_only = pytest.mark.skipif(os.name != "posix", reason="POSIX file modes only")


def _mode(path) -> int:
    return stat.S_IMODE(os.stat(path).st_mode)


@pytest.fixture
def umask022():
    previous = os.umask(0o022)
    try:
        yield
    finally:
        os.umask(previous)


@posix_only
def test_new_database_is_private(tmp_path, umask022):
    db_path = tmp_path / "sub" / "db.sqlite"

    SQLiteConnection(db_path=db_path)

    assert _mode(db_path) == 0o600
    for suffix in ("-wal", "-shm"):
        side = db_path.with_name(db_path.name + suffix)
        if side.exists():
            assert _mode(side) == 0o600


@posix_only
def test_existing_database_is_tightened(tmp_path, umask022):
    db_path = tmp_path / "db.sqlite"
    sqlite3.connect(str(db_path)).close()
    os.chmod(db_path, 0o644)

    SQLiteConnection(db_path=db_path)

    assert _mode(db_path) == 0o600


@posix_only
def test_existing_wal_side_files_are_tightened(tmp_path, umask022):
    db_path = tmp_path / "db.sqlite"
    held = sqlite3.connect(str(db_path))
    try:
        held.execute("PRAGMA journal_mode=WAL")
        held.execute("CREATE TABLE t (x)")
        held.commit()
        wal = db_path.with_name(db_path.name + "-wal")
        shm = db_path.with_name(db_path.name + "-shm")
        assert wal.exists() and shm.exists()
        for path in (db_path, wal, shm):
            os.chmod(path, 0o644)

        SQLiteConnection(db_path=db_path)

        assert _mode(db_path) == 0o600
        assert _mode(wal) == 0o600
        assert _mode(shm) == 0o600
    finally:
        held.close()


@posix_only
def test_legacy_default_install_is_tightened(tmp_path, monkeypatch, umask022):
    fake_home = tmp_path / "home"
    app_dir = fake_home / ".simple_iptv"
    app_dir.mkdir(parents=True)
    os.chmod(app_dir, 0o755)
    db_path = app_dir / "database.db"
    sqlite3.connect(str(db_path)).close()
    os.chmod(db_path, 0o644)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    SQLiteConnection()

    assert _mode(app_dir) == 0o700
    assert _mode(db_path) == 0o600


@posix_only
def test_caller_supplied_parent_directory_mode_is_untouched(tmp_path, umask022):
    os.chmod(tmp_path, 0o755)

    SQLiteConnection(db_path=tmp_path / "db.sqlite")

    assert _mode(tmp_path) == 0o755


@posix_only
def test_default_location_is_private(tmp_path, monkeypatch, umask022):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    conn = SQLiteConnection()

    app_dir = fake_home / ".simple_iptv"
    assert conn.db_path == app_dir / "database.db"
    assert _mode(app_dir) == 0o700
    assert _mode(conn.db_path) == 0o600


@posix_only
def test_chmod_failure_does_not_prevent_startup(tmp_path, monkeypatch, caplog, umask022):
    def failing_chmod(*args, **kwargs):
        raise OSError("denied")

    monkeypatch.setattr(os, "chmod", failing_chmod)

    with caplog.at_level(logging.WARNING):
        conn = SQLiteConnection(db_path=tmp_path / "db.sqlite")

    assert conn.db_path.exists()
    assert "Could not set permissions" in caplog.text
