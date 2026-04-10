import logging
from typing import Iterable, List, Sequence

from core.errors import RepositoryError
from core.models import PlaylistReference, PlaylistSourceType, XtreamCredentials
from infra.db.sqlite_connection import SQLiteConnection


logger = logging.getLogger(__name__)


class PlaylistRepository:
    def __init__(self, db: SQLiteConnection):
        self.db = db

    def save_playlists(self, playlists: Sequence[PlaylistReference]) -> None:
        try:
            with self.db.get_connection() as conn:
                conn.execute("DELETE FROM playlists")
                for playlist in playlists:
                    self._insert_playlist(conn, playlist)
        except Exception as exc:
            logger.error("Failed to save playlists: %s", exc)
            raise RepositoryError("Failed to save playlists") from exc

    def get_playlists(self) -> List[PlaylistReference]:
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT
                        name,
                        source_type,
                        path,
                        is_url,
                        source_identity,
                        xtream_server_url,
                        xtream_username,
                        xtream_password,
                        xtream_output,
                        channel_count,
                        last_loaded_at,
                        last_status,
                        last_error
                    FROM playlists
                    ORDER BY
                        CASE WHEN last_loaded_at = '' THEN 1 ELSE 0 END,
                        last_loaded_at DESC,
                        name COLLATE NOCASE ASC
                    """
                )
                return [self._row_to_reference(row) for row in cursor.fetchall()]
        except Exception as exc:
            logger.error("Failed to load playlists: %s", exc)
            raise RepositoryError("Failed to load playlists") from exc

    def upsert_playlist(self, playlist: PlaylistReference) -> None:
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO playlists (
                        name,
                        source_type,
                        path,
                        is_url,
                        source_identity,
                        xtream_server_url,
                        xtream_username,
                        xtream_password,
                        xtream_output,
                        channel_count,
                        last_loaded_at,
                        last_status,
                        last_error
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_identity) DO UPDATE SET
                        name = excluded.name,
                        source_type = excluded.source_type,
                        path = excluded.path,
                        is_url = excluded.is_url,
                        xtream_server_url = excluded.xtream_server_url,
                        xtream_username = excluded.xtream_username,
                        xtream_password = CASE
                            WHEN excluded.xtream_password = '' THEN playlists.xtream_password
                            ELSE excluded.xtream_password
                        END,
                        xtream_output = excluded.xtream_output
                    """,
                    self._playlist_values(playlist),
                )
        except Exception as exc:
            logger.error("Failed to upsert playlist %s: %s", playlist.source_identity, exc)
            raise RepositoryError("Failed to upsert playlist") from exc

    def delete_playlist(self, identity: str) -> None:
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    "DELETE FROM playlists WHERE source_identity = ?",
                    (identity,),
                )
        except Exception as exc:
            logger.error("Failed to delete playlist %s: %s", identity, exc)
            raise RepositoryError("Failed to delete playlist") from exc

    def get_playlist_by_identity(self, identity: str) -> PlaylistReference | None:
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT
                        name,
                        source_type,
                        path,
                        is_url,
                        source_identity,
                        xtream_server_url,
                        xtream_username,
                        xtream_password,
                        xtream_output,
                        channel_count,
                        last_loaded_at,
                        last_status,
                        last_error
                    FROM playlists
                    WHERE source_identity = ?
                    """,
                    (identity,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return self._row_to_reference(row)
        except Exception as exc:
            logger.error("Failed to load playlist %s: %s", identity, exc)
            raise RepositoryError("Failed to load playlist") from exc

    def import_playlists(self, playlists: Iterable[PlaylistReference]) -> None:
        self.save_playlists(list(playlists))

    def update_playlist_metadata(
        self,
        identity: str,
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
                    WHERE source_identity = ?
                    """,
                    (channel_count, last_loaded_at, last_status, last_error, identity),
                )
        except Exception as exc:
            logger.error("Failed to update playlist metadata for %s: %s", identity, exc)
            raise RepositoryError("Failed to update playlist metadata") from exc

    def _insert_playlist(self, conn, playlist: PlaylistReference) -> None:
        conn.execute(
            """
            INSERT INTO playlists (
                name,
                source_type,
                path,
                is_url,
                source_identity,
                xtream_server_url,
                xtream_username,
                xtream_password,
                xtream_output,
                channel_count,
                last_loaded_at,
                last_status,
                last_error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._playlist_values(playlist),
        )

    @staticmethod
    def _playlist_values(playlist: PlaylistReference) -> tuple[object, ...]:
        xtream = playlist.normalized_xtream() if playlist.source_type == PlaylistSourceType.XTREAM else None
        return (
            playlist.name,
            playlist.source_type.value,
            playlist.normalized_url() if playlist.source_type == PlaylistSourceType.URL else playlist.normalized_path() if playlist.source_type == PlaylistSourceType.FILE else "",
            1 if playlist.source_type == PlaylistSourceType.URL else 0,
            playlist.source_identity,
            xtream.server_url if xtream else "",
            xtream.username if xtream else "",
            xtream.password if xtream else "",
            xtream.output if xtream else "",
            playlist.channel_count,
            playlist.last_loaded_at,
            playlist.last_status,
            playlist.last_error,
        )

    @staticmethod
    def _row_to_reference(row) -> PlaylistReference:
        source_type = PlaylistSourceType(row["source_type"])
        xtream = None
        if source_type == PlaylistSourceType.XTREAM:
            xtream = XtreamCredentials(
                server_url=row["xtream_server_url"] or "",
                username=row["xtream_username"] or "",
                password=row["xtream_password"] or "",
                output=row["xtream_output"] or "ts",
            )
        return PlaylistReference(
            name=row["name"],
            path=row["path"] or "",
            source_type=source_type,
            xtream=xtream,
            channel_count=row["channel_count"] or 0,
            last_loaded_at=row["last_loaded_at"] or "",
            last_status=row["last_status"] or "",
            last_error=row["last_error"] or "",
        )
