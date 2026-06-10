import logging
from datetime import datetime
from typing import List

from core.errors import RepositoryError
from core.models import Channel
from infra.db.sqlite_connection import SQLiteConnection

logger = logging.getLogger(__name__)


class HistoryRepository:
    def __init__(self, db: SQLiteConnection):
        self.db = db

    def record_channel(self, channel: Channel, playlist_path: str, played_at: int) -> None:
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO recent_channels
                    (url, playlist_path, name, group_name, logo, epg_id, played_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(url, playlist_path) DO UPDATE SET
                        name = excluded.name,
                        group_name = excluded.group_name,
                        logo = excluded.logo,
                        epg_id = excluded.epg_id,
                        played_at = excluded.played_at
                    """,
                    (
                        channel.url,
                        playlist_path,
                        channel.name,
                        channel.group,
                        channel.logo,
                        channel.epg_id,
                        played_at,
                    ),
                )
        except Exception as exc:
            logger.error("Failed to record channel history %s: %s", channel.url, exc)
            raise RepositoryError("Failed to record recent channel") from exc

    def get_recent_channels(self, limit: int = 12) -> List[Channel]:
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT name, url, group_name, logo, epg_id, playlist_path, played_at
                    FROM recent_channels
                    ORDER BY played_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                return [
                    Channel(
                        name=row["name"],
                        url=row["url"],
                        group=row["group_name"] or "",
                        logo=row["logo"] or "",
                        epg_id=row["epg_id"] or "",
                        playlist_path=row["playlist_path"] or "",
                        last_played_at=row["played_at"],
                    )
                    for row in cursor.fetchall()
                ]
        except Exception as exc:
            logger.error("Failed to read recent channels: %s", exc)
            raise RepositoryError("Failed to read recent channels") from exc

    def get_last_played_at(self) -> datetime | None:
        try:
            with self.db.get_connection() as conn:
                row = conn.execute("SELECT MAX(played_at) AS played_at FROM recent_channels").fetchone()
                if not row or row["played_at"] is None:
                    return None
                return datetime.fromtimestamp(row["played_at"])
        except Exception as exc:
            logger.error("Failed to query playback history timestamp: %s", exc)
            raise RepositoryError("Failed to query playback history") from exc
