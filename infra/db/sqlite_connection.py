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
                        is_url BOOLEAN NOT NULL DEFAULT 0,
                        channel_count INTEGER NOT NULL DEFAULT 0,
                        last_loaded_at TEXT NOT NULL DEFAULT '',
                        last_status TEXT NOT NULL DEFAULT '',
                        last_error TEXT NOT NULL DEFAULT ''
                    );
                    CREATE UNIQUE INDEX IF NOT EXISTS ux_playlists_path ON playlists (path);
                    
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
                    CREATE INDEX IF NOT EXISTS ix_epg_channel_time
                        ON epg_data (channel_id, start_time, end_time);
                    
                    CREATE TABLE IF NOT EXISTS favorites (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        url TEXT NOT NULL,
                        playlist_path TEXT NOT NULL DEFAULT '',
                        group_name TEXT,
                        logo TEXT,
                        epg_id TEXT,
                        UNIQUE (url, playlist_path)
                    );

                    CREATE TABLE IF NOT EXISTS recent_channels (
                        url TEXT NOT NULL,
                        playlist_path TEXT NOT NULL,
                        name TEXT NOT NULL,
                        group_name TEXT,
                        logo TEXT,
                        epg_id TEXT,
                        played_at INTEGER NOT NULL,
                        PRIMARY KEY (url, playlist_path)
                    );
                    CREATE INDEX IF NOT EXISTS ix_recent_channels_played_at
                        ON recent_channels (played_at DESC);
                    
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('last_playlist', '');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('last_playlist_path', '');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('last_epg_file', '');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('last_epg_path', '');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('epg_url', '');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('last_epg_url', '');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('last_epg_loaded_at', '');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('last_playlist_is_url', 'false');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('theme', 'dark');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('volume', '100');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('is_muted', 'false');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('last_channel_url', '');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('last_channel_group', '');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('window_width', '1280');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('window_height', '720');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('play_on_single_click', 'false');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('show_now_playing_in_list', 'true');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('search_current_category_only', 'true');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('channel_sort_mode', 'name_asc');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('splitter_sizes', '390,960');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('active_tab_index', '0');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('selected_category', 'All');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('search_text', '');
                    INSERT OR IGNORE INTO settings (key, value) VALUES ('left_panel_visible', 'true');
                """)
                self._ensure_column(conn, "playlists", "channel_count", "INTEGER NOT NULL DEFAULT 0")
                self._ensure_column(conn, "playlists", "last_loaded_at", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(conn, "playlists", "last_status", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(conn, "playlists", "last_error", "TEXT NOT NULL DEFAULT ''")
                self._ensure_favorites_table(conn)
                logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, definition: str) -> None:
        columns = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in columns:
            return
        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
        )

    @staticmethod
    def _ensure_favorites_table(conn: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(favorites)").fetchall()
        }
        if "playlist_path" in columns:
            conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_favorites_identity ON favorites (url, playlist_path)"
            )
            return

        conn.executescript(
            """
            ALTER TABLE favorites RENAME TO favorites_legacy;
            CREATE TABLE favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                playlist_path TEXT NOT NULL DEFAULT '',
                group_name TEXT,
                logo TEXT,
                epg_id TEXT,
                UNIQUE (url, playlist_path)
            );
            CREATE INDEX IF NOT EXISTS ix_favorites_identity
                ON favorites (url, playlist_path);
            INSERT INTO favorites (name, url, playlist_path, group_name, logo, epg_id)
            SELECT name, url, '', group_name, logo, epg_id
            FROM favorites_legacy;
            DROP TABLE favorites_legacy;
            """
        )
