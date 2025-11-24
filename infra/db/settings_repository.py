from infra.db.sqlite_connection import SQLiteConnection

class SettingsRepository:
    def __init__(self, db: SQLiteConnection):
        self.db = db

    def save_setting(self, key: str, value: str) -> None:
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (key, value)
                )
        except Exception:
            pass

    def get_setting(self, key: str, default: str = "") -> str:
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
                row = cursor.fetchone()
                return row["value"] if row else default
        except Exception:
            return default
