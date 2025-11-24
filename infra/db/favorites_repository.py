from typing import List
from infra.db.sqlite_connection import SQLiteConnection
from core.models import Channel

class FavoritesRepository:
    def __init__(self, db: SQLiteConnection):
        self.db = db

    def add_favorite(self, channel: Channel) -> bool:
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO favorites 
                       (name, url, group_name, logo, epg_id) 
                       VALUES (?, ?, ?, ?, ?)""",
                    (channel.name, channel.url, channel.group, channel.logo, channel.epg_id)
                )
            return True
        except Exception:
            return False

    def remove_favorite(self, url: str) -> bool:
        try:
            with self.db.get_connection() as conn:
                conn.execute("DELETE FROM favorites WHERE url = ?", (url,))
            return True
        except Exception:
            return False

    def get_favorites(self) -> List[Channel]:
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM favorites")
                return [Channel(
                    name=row["name"],
                    url=row["url"],
                    group=row["group_name"],
                    logo=row["logo"],
                    epg_id=row["epg_id"]
                ) for row in cursor.fetchall()]
        except Exception:
            return []

    def is_favorite(self, url: str) -> bool:
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("SELECT 1 FROM favorites WHERE url = ?", (url,))
                return cursor.fetchone() is not None
        except Exception:
            return False
