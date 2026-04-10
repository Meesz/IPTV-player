import logging
from typing import Iterable, List, Sequence, Tuple

from infra.db.sqlite_connection import SQLiteConnection
from core.errors import RepositoryError
from core.models import PlaylistReference


logger = logging.getLogger(__name__)

class PlaylistRepository:
    def __init__(self, db: SQLiteConnection):
        self.db = db

    def save_playlists(self, playlists: Sequence[Tuple[str, str, bool]]) -> None:
        """Save a list of playlists (name, path, is_url)."""
        try:
            with self.db.get_connection() as conn:
                conn.execute("DELETE FROM playlists")
                for name, path, is_url in playlists:
                    conn.execute(
                        "INSERT INTO playlists (name, path, is_url) VALUES (?, ?, ?)",
                        (name, path, 1 if is_url else 0)
                    )
        except Exception as exc:
            logger.error("Failed to save playlists: %s", exc)
            raise RepositoryError("Failed to save playlists") from exc

    def get_playlists(self) -> List[PlaylistReference]:
        """Retrieve all playlists."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("SELECT name, path, is_url FROM playlists")
                return [
                    PlaylistReference(
                        name=row["name"],
                        path=row["path"],
                        is_url=bool(row["is_url"]),
                    )
                    for row in cursor.fetchall()
                ]
        except Exception as exc:
            logger.error("Failed to load playlists: %s", exc)
            raise RepositoryError("Failed to load playlists") from exc

    def upsert_playlist(self, playlist: PlaylistReference) -> None:
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO playlists (name, path, is_url)
                    VALUES (?, ?, ?)
                    ON CONFLICT(path) DO UPDATE SET
                        name = excluded.name,
                        is_url = excluded.is_url
                    """,
                    (playlist.name, playlist.path, 1 if playlist.is_url else 0),
                )
        except Exception as exc:
            logger.error("Failed to upsert playlist %s: %s", playlist.path, exc)
            raise RepositoryError("Failed to upsert playlist") from exc

    def delete_playlist(self, path: str) -> None:
        try:
            with self.db.get_connection() as conn:
                conn.execute("DELETE FROM playlists WHERE path = ?", (path,))
        except Exception as exc:
            logger.error("Failed to delete playlist %s: %s", path, exc)
            raise RepositoryError("Failed to delete playlist") from exc

    def get_playlist(self, path: str) -> PlaylistReference | None:
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT name, path, is_url FROM playlists WHERE path = ?",
                    (path,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return PlaylistReference(
                    name=row["name"],
                    path=row["path"],
                    is_url=bool(row["is_url"]),
                )
        except Exception as exc:
            logger.error("Failed to get playlist %s: %s", path, exc)
            raise RepositoryError("Failed to load playlist") from exc

    def import_playlists(self, playlists: Iterable[PlaylistReference]) -> None:
        records = [(item.name, item.path, item.is_url) for item in playlists]
        self.save_playlists(records)
