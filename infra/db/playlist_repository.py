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
                existing_rows = conn.execute(
                    """
                    SELECT path, channel_count, last_loaded_at, last_status, last_error
                    FROM playlists
                    """
                ).fetchall()
                existing_metadata = {
                    row["path"]: (
                        row["channel_count"],
                        row["last_loaded_at"],
                        row["last_status"],
                        row["last_error"],
                    )
                    for row in existing_rows
                }
                conn.execute("DELETE FROM playlists")
                for name, path, is_url in playlists:
                    channel_count, last_loaded_at, last_status, last_error = existing_metadata.get(
                        path,
                        (0, "", "", ""),
                    )
                    conn.execute(
                        """
                        INSERT INTO playlists
                        (name, path, is_url, channel_count, last_loaded_at, last_status, last_error)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            name,
                            path,
                            1 if is_url else 0,
                            channel_count,
                            last_loaded_at,
                            last_status,
                            last_error,
                        ),
                    )
        except Exception as exc:
            logger.error("Failed to save playlists: %s", exc)
            raise RepositoryError("Failed to save playlists") from exc

    def get_playlists(self) -> List[PlaylistReference]:
        """Retrieve all playlists."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT name, path, is_url, channel_count, last_loaded_at, last_status, last_error
                    FROM playlists
                    ORDER BY
                        CASE WHEN last_loaded_at = '' THEN 1 ELSE 0 END,
                        last_loaded_at DESC,
                        name COLLATE NOCASE ASC
                    """
                )
                return [
                    PlaylistReference(
                        name=row["name"],
                        path=row["path"],
                        is_url=bool(row["is_url"]),
                        channel_count=row["channel_count"] or 0,
                        last_loaded_at=row["last_loaded_at"] or "",
                        last_status=row["last_status"] or "",
                        last_error=row["last_error"] or "",
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
                    INSERT INTO playlists
                    (name, path, is_url, channel_count, last_loaded_at, last_status, last_error)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(path) DO UPDATE SET
                        name = excluded.name,
                        is_url = excluded.is_url
                    """,
                    (
                        playlist.name,
                        playlist.path,
                        1 if playlist.is_url else 0,
                        playlist.channel_count,
                        playlist.last_loaded_at,
                        playlist.last_status,
                        playlist.last_error,
                    ),
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
                    """
                    SELECT name, path, is_url, channel_count, last_loaded_at, last_status, last_error
                    FROM playlists
                    WHERE path = ?
                    """,
                    (path,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return PlaylistReference(
                    name=row["name"],
                    path=row["path"],
                    is_url=bool(row["is_url"]),
                    channel_count=row["channel_count"] or 0,
                    last_loaded_at=row["last_loaded_at"] or "",
                    last_status=row["last_status"] or "",
                    last_error=row["last_error"] or "",
                )
        except Exception as exc:
            logger.error("Failed to get playlist %s: %s", path, exc)
            raise RepositoryError("Failed to load playlist") from exc

    def import_playlists(self, playlists: Iterable[PlaylistReference]) -> None:
        records = [(item.name, item.path, item.is_url) for item in playlists]
        self.save_playlists(records)

    def update_playlist_metadata(
        self,
        path: str,
        *,
        channel_count: int,
        last_loaded_at: str,
        last_status: str,
        last_error: str = "",
    ) -> None:
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    UPDATE playlists
                    SET channel_count = ?,
                        last_loaded_at = ?,
                        last_status = ?,
                        last_error = ?
                    WHERE path = ?
                    """,
                    (channel_count, last_loaded_at, last_status, last_error, path),
                )
        except Exception as exc:
            logger.error("Failed to update playlist metadata for %s: %s", path, exc)
            raise RepositoryError("Failed to update playlist metadata") from exc
