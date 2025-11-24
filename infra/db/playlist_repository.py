from typing import List, Tuple
from infra.db.sqlite_connection import SQLiteConnection

class PlaylistRepository:
    def __init__(self, db: SQLiteConnection):
        self.db = db

    def save_playlists(self, playlists: List[Tuple[str, str, bool]]) -> bool:
        """Save a list of playlists (name, path, is_url)."""
        try:
            with self.db.get_connection() as conn:
                conn.execute("DELETE FROM playlists")
                for name, path, is_url in playlists:
                    conn.execute(
                        "INSERT INTO playlists (name, path, is_url) VALUES (?, ?, ?)",
                        (name, path, 1 if is_url else 0)
                    )
            return True
        except Exception:
            return False

    def get_playlists(self) -> List[Tuple[str, str, bool]]:
        """Retrieve all playlists."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("SELECT name, path, is_url FROM playlists")
                return [(row["name"], row["path"], bool(row["is_url"])) for row in cursor.fetchall()]
        except Exception:
            return []
