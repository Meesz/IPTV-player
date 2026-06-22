import logging

from core.errors import RepositoryError
from core.models import Channel
from infra.db.sqlite_connection import SQLiteConnection

logger = logging.getLogger(__name__)


class FavoritesRepository:
    def __init__(self, db: SQLiteConnection):
        self.db = db

    def add_favorite(self, channel: Channel) -> bool:
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO favorites
                       (name, url, playlist_path, group_name, logo, epg_id)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        channel.name,
                        channel.url,
                        channel.playlist_path or "",
                        channel.group,
                        channel.logo,
                        channel.epg_id,
                    ),
                )
            return True
        except Exception as exc:
            logger.error("Failed to add favorite %s: %s", channel.url, exc)
            raise RepositoryError("Failed to add favorite") from exc

    def remove_favorite(self, channel: Channel) -> bool:
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    "DELETE FROM favorites WHERE url = ? AND playlist_path = ?",
                    (channel.url, channel.playlist_path or ""),
                )
            return True
        except Exception as exc:
            logger.error("Failed to remove favorite %s: %s", channel.url, exc)
            raise RepositoryError("Failed to remove favorite") from exc

    def get_favorites(self) -> list[Channel]:
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM favorites")
                return [
                    Channel(
                        name=row["name"],
                        url=row["url"],
                        playlist_path=row["playlist_path"] or "",
                        group=row["group_name"],
                        logo=row["logo"],
                        epg_id=row["epg_id"],
                    )
                    for row in cursor.fetchall()
                ]
        except Exception as exc:
            logger.error("Failed to read favorites: %s", exc)
            raise RepositoryError("Failed to read favorites") from exc

    def is_favorite(self, channel: Channel) -> bool:
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM favorites WHERE url = ? AND playlist_path = ?",
                    (channel.url, channel.playlist_path or ""),
                )
                return cursor.fetchone() is not None
        except Exception as exc:
            logger.error("Failed to check favorite %s: %s", channel.url, exc)
            raise RepositoryError("Failed to check favorite") from exc
