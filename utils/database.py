"""
This module provides utilities for managing the database.
It defines the Database class, which can handle database operations.
"""

import sqlite3
from typing import List, Optional, Dict, Any
from datetime import datetime
from contextlib import contextmanager
from queue import Queue
import threading
import logging
from models.epg import Program
from config import Config


class DatabaseConnectionPool:
    """A thread-safe connection pool for SQLite database connections."""

    def __init__(self, database_path: str, max_connections: int = 5):
        """Initialize the connection pool."""
        self.database_path = database_path
        self.max_connections = max_connections
        self.connections: Queue[sqlite3.Connection] = Queue(maxsize=max_connections)
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

        # Initialize connection pool
        for _ in range(max_connections):
            self.connections.put(self._create_connection())

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection with proper configuration."""
        connection = sqlite3.connect(
            self.database_path,
            timeout=Config.DB_TIMEOUT,
            isolation_level=None,  # Enable autocommit mode
        )
        connection.row_factory = sqlite3.Row
        # Enable foreign key support
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def get_connection(self):
        """Get a connection from the pool."""
        connection = None
        try:
            connection = self.connections.get(timeout=Config.DB_TIMEOUT)
            yield connection
        except Exception as e:
            self.logger.error(f"Database connection error: {e}")
            # If the connection is broken, create a new one
            if connection:
                try:
                    connection.close()
                except Exception:
                    pass
                connection = self._create_connection()
            raise
        finally:
            if connection:
                self.connections.put(connection)


class Database:
    """Database management class with connection pooling."""

    def __init__(self):
        """Initialize the database with connection pool."""
        self.pool = DatabaseConnectionPool(
            str(Config.DATABASE_PATH), max_connections=Config.DB_MAX_CONNECTIONS
        )
        self.logger = logging.getLogger(__name__)
        self._initialize_database()

    def _initialize_database(self):
        """Initialize database tables if they don't exist."""
        with self.pool.get_connection() as conn:
            conn.executescript(
                """
                BEGIN;
                
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    is_url BOOLEAN NOT NULL DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS favorites (
                    url TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_favorites_category ON favorites(category);
                
                COMMIT;
            """
            )

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a setting value by key."""
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT value FROM settings WHERE key = ?", (key,)
                )
                result = cursor.fetchone()
                return result[0] if result else default
        except Exception as e:
            self.logger.error(f"Error getting setting {key}: {e}")
            return default

    def save_setting(self, key: str, value: str) -> bool:
        """Save a setting value."""
        try:
            with self.pool.get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO settings (key, value)
                    VALUES (?, ?)
                """,
                    (key, value),
                )
                return True
        except Exception as e:
            self.logger.error(f"Error saving setting {key}: {e}")
            return False

    def get_playlists(self) -> List[Dict[str, Any]]:
        """Get all saved playlists."""
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT id, name, path, is_url, last_updated
                    FROM playlists
                    ORDER BY last_updated DESC
                """
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            self.logger.error(f"Error getting playlists: {e}")
            return []

    def save_playlists(self, playlists: List[Dict[str, Any]]) -> bool:
        """Save multiple playlists."""
        try:
            with self.pool.get_connection() as conn:
                conn.execute("BEGIN")
                conn.execute("DELETE FROM playlists")

                conn.executemany(
                    """
                    INSERT INTO playlists (name, path, is_url)
                    VALUES (:name, :path, :is_url)
                """,
                    playlists,
                )

                conn.execute("COMMIT")
                return True
        except Exception as e:
            self.logger.error(f"Error saving playlists: {e}")
            return False

    def add_favorite(self, channel_url: str, channel_name: str, category: str) -> bool:
        """Add a channel to favorites."""
        try:
            with self.pool.get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO favorites (url, name, category)
                    VALUES (?, ?, ?)
                """,
                    (channel_url, channel_name, category),
                )
                return True
        except Exception as e:
            self.logger.error(f"Error adding favorite: {e}")
            return False

    def remove_favorite(self, channel_url: str) -> bool:
        """Remove a channel from favorites."""
        try:
            with self.pool.get_connection() as conn:
                conn.execute("DELETE FROM favorites WHERE url = ?", (channel_url,))
                return True
        except Exception as e:
            self.logger.error(f"Error removing favorite: {e}")
            return False

    def get_favorites(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get favorite channels, optionally filtered by category."""
        try:
            with self.pool.get_connection() as conn:
                if category and category != Config.DEFAULT_CATEGORY:
                    cursor = conn.execute(
                        """
                        SELECT url, name, category, added_date
                        FROM favorites
                        WHERE category = ?
                        ORDER BY name
                    """,
                        (category,),
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT url, name, category, added_date
                        FROM favorites
                        ORDER BY name
                    """
                    )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            self.logger.error(f"Error getting favorites: {e}")
            return []

    def is_favorite(self, channel_url: str) -> bool:
        """Check if a channel is in favorites."""
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM favorites WHERE url = ?", (channel_url,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            self.logger.error(f"Error checking favorite status: {e}")
            return False

    def save_epg_program(self, channel_id: str, program: Program):
        """Save an EPG program to the database.

        Args:
            channel_id (str): The ID of the channel.
            program (Program): The EPG program to save.
        """
        try:
            with self.pool.get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO epg_data 
                    (channel_id, start_time, end_time, title, description)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        channel_id,
                        int(program.start_time.timestamp()),
                        int(program.end_time.timestamp()),
                        program.title,
                        program.description,
                    ),
                )
            return True
        except sqlite3.Error:
            return False

    def get_current_program(self, channel_id: str) -> Optional[Program]:
        """Retrieve the current EPG program for a channel.

        Args:
            channel_id (str): The ID of the channel.

        Returns:
            Optional[Program]: The current EPG program if found, otherwise None.
        """
        try:
            current_time = int(datetime.now().timestamp())
            with self.pool.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT * FROM epg_data 
                    WHERE channel_id = ? 
                    AND start_time <= ? 
                    AND end_time > ?
                """,
                    (channel_id, current_time, current_time),
                )

                row = cursor.fetchone()
                if row:
                    return Program(
                        title=row["title"],
                        start_time=datetime.fromtimestamp(row["start_time"]),
                        end_time=datetime.fromtimestamp(row["end_time"]),
                        description=row["description"],
                    )
            return None
        except sqlite3.Error:
            return None

    def get_upcoming_programs(self, channel_id: str, limit: int = 5) -> List[Program]:
        """Retrieve upcoming EPG programs for a channel.

        Args:
            channel_id (str): The ID of the channel.
            limit (int, optional): The maximum number of programs to retrieve. Defaults to 5.

        Returns:
            List[Program]: A list of upcoming EPG programs.
        """
        try:
            current_time = int(datetime.now().timestamp())
            with self.pool.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT * FROM epg_data 
                    WHERE channel_id = ? 
                    AND end_time > ?
                    ORDER BY start_time
                    LIMIT ?
                """,
                    (channel_id, current_time, limit),
                )

                return [
                    Program(
                        title=row["title"],
                        start_time=datetime.fromtimestamp(row["start_time"]),
                        end_time=datetime.fromtimestamp(row["end_time"]),
                        description=row["description"],
                    )
                    for row in cursor.fetchall()
                ]
        except sqlite3.Error:
            return []

    def clear_setting(self, key: str):
        """Clear a setting from the database."""
        self.save_setting(key, "")
