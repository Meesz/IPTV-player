import sqlite3
import logging
from pathlib import Path
from typing import Optional, Generator
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class SQLiteConnection:
    """Manages SQLite database connection and initialization."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            self.db_path = Path.home() / ".simple_iptv" / "database.db"
        else:
            self.db_path = db_path
        
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection context manager."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def _init_database(self):
        """Initialize the database with required tables."""
        try:
            with self.get_connection() as conn:
                # Enable WAL mode
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA cache_size=-2000")
                conn.execute("PRAGMA temp_store=MEMORY")

                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS playlists (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        path TEXT NOT NULL,
                        is_url BOOLEAN NOT NULL DEFAULT 0
                    );
                    
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    );
                    
                    CREATE TABLE IF NOT EXISTS epg_data (
                        channel_id TEXT,
                        start_time INTEGER,
                        end_time INTEGER,
                        title TEXT,
                        description TEXT,
                        PRIMARY KEY (channel_id, start_time)
                    );
                    
                    CREATE TABLE IF NOT EXISTS favorites (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        url TEXT NOT NULL UNIQUE,
                        group_name TEXT,
                        logo TEXT,
                        epg_id TEXT
                    );
                    
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('last_playlist', '');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('last_epg_file', '');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('epg_url', '');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('last_playlist_is_url', 'false');
                """)
                logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
