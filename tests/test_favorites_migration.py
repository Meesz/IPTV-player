"""Legacy favourites table (no playlist_path column) is migrated without losing rows."""

import sqlite3

import pytest

from core.models import Channel
from infra.db.favorites_repository import FavoritesRepository
from infra.db.sqlite_connection import SQLiteConnection


def _create_legacy_db(db_path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                group_name TEXT,
                logo TEXT,
                epg_id TEXT
            );
            INSERT INTO favorites (name, url, group_name, logo, epg_id)
            VALUES ('News One', 'http://example.com/one', 'News', 'logo.png', 'news.one');
            INSERT INTO favorites (name, url, group_name, logo, epg_id)
            VALUES ('Sports Two', 'http://example.com/two', 'Sports', '', '');
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_legacy_favorites_survive_migration_with_empty_playlist_path(tmp_path):
    db_path = tmp_path / "legacy.sqlite"
    _create_legacy_db(db_path)

    repository = FavoritesRepository(SQLiteConnection(db_path=db_path))
    favorites = {favorite.url: favorite for favorite in repository.get_favorites()}

    assert set(favorites) == {"http://example.com/one", "http://example.com/two"}
    one = favorites["http://example.com/one"]
    assert (one.name, one.group, one.logo, one.epg_id) == ("News One", "News", "logo.png", "news.one")
    assert one.playlist_path == ""
    assert repository.is_favorite(Channel(name="News One", url="http://example.com/one"))


def test_migrated_favorites_are_unique_per_url_and_playlist_path(tmp_path):
    db_path = tmp_path / "legacy.sqlite"
    _create_legacy_db(db_path)
    connection = SQLiteConnection(db_path=db_path)
    repository = FavoritesRepository(connection)

    # Same (url, playlist_path) replaces the migrated row instead of duplicating it.
    repository.add_favorite(Channel(name="News One renamed", url="http://example.com/one"))
    assert [f.name for f in repository.get_favorites() if f.url == "http://example.com/one"] == ["News One renamed"]

    # The same URL from a different playlist is a distinct favourite.
    other = Channel(name="News One", url="http://example.com/one", playlist_path="file::/lists/a.m3u")
    repository.add_favorite(other)
    assert len(repository.get_favorites()) == 3
    assert repository.is_favorite(other)

    # The schema itself enforces UNIQUE (url, playlist_path).
    with connection.get_connection() as conn, pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO favorites (name, url, playlist_path) VALUES ('dup', 'http://example.com/two', '')")


def test_migration_is_idempotent_on_reopen(tmp_path):
    db_path = tmp_path / "legacy.sqlite"
    _create_legacy_db(db_path)
    SQLiteConnection(db_path=db_path)

    repository = FavoritesRepository(SQLiteConnection(db_path=db_path))

    assert len(repository.get_favorites()) == 2
