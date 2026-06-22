"""Migration-robustness tests for the embedded SQLite schema upgrade.

Qt-free so they run without the PyQt6 runtime. They guard the fix that stopped
a legacy `playlists` migration from aborting startup (and locking the user out
of the whole database) when two legacy paths collapse to one source identity.
"""

import sqlite3

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
