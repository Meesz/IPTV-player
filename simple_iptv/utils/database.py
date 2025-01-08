import sqlite3
from pathlib import Path
from typing import List, Optional
from dataclasses import asdict
from models.playlist import Channel
from models.epg import Program
from datetime import datetime

class Database:
    def __init__(self):
        self.db_path = Path.home() / '.simple_iptv' / 'database.db'
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = None
        self.init_database()
    
    def _get_connection(self):
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path)
            self._connection.row_factory = sqlite3.Row
        return self._connection
    
    def close(self):
        if self._connection:
            self._connection.close()
            self._connection = None
    
    def init_database(self):
        with self._get_connection() as conn:
            # Enable WAL mode for better performance
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA cache_size=-2000')  # Use 2MB cache
            conn.execute('PRAGMA temp_store=MEMORY')
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    group_name TEXT,
                    logo TEXT,
                    epg_id TEXT
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
                
                -- Add default settings for file paths
                INSERT OR IGNORE INTO settings (key, value) VALUES ('last_playlist', '');
                INSERT OR IGNORE INTO settings (key, value) VALUES ('last_epg_file', '');
                INSERT OR IGNORE INTO settings (key, value) VALUES ('last_epg_url', '');
            ''')
    
    def add_favorite(self, channel: Channel) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    '''INSERT OR REPLACE INTO favorites 
                       (name, url, group_name, logo) 
                       VALUES (?, ?, ?, ?)''',
                    (channel.name, channel.url, channel.group, channel.logo)
                )
                return True
        except sqlite3.Error as e:
            print(f"Database error: {str(e)}")
            return False
    
    def remove_favorite(self, url: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('DELETE FROM favorites WHERE url = ?', (url,))
            return True
        except sqlite3.Error:
            return False
    
    def get_favorites(self) -> List[Channel]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('SELECT * FROM favorites')
                return [Channel.from_db_row(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Database error: {str(e)}")
            return []
    
    def is_favorite(self, url: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT 1 FROM favorites WHERE url = ?', (url,))
                return cursor.fetchone() is not None
        except sqlite3.Error:
            return False
    
    def save_setting(self, key: str, value: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    'INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
                    (key, value)
                )
        except sqlite3.Error:
            pass
    
    def get_setting(self, key: str, default: str = "") -> str:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT value FROM settings WHERE key = ?', (key,))
                result = cursor.fetchone()
                return result[0] if result else default
        except sqlite3.Error:
            return default 
    
    def save_epg_program(self, channel_id: str, program: Program):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO epg_data 
                    (channel_id, start_time, end_time, title, description)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    channel_id,
                    int(program.start_time.timestamp()),
                    int(program.end_time.timestamp()),
                    program.title,
                    program.description
                ))
            return True
        except sqlite3.Error:
            return False
    
    def get_current_program(self, channel_id: str) -> Optional[Program]:
        try:
            current_time = int(datetime.now().timestamp())
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT * FROM epg_data 
                    WHERE channel_id = ? 
                    AND start_time <= ? 
                    AND end_time > ?
                ''', (channel_id, current_time, current_time))
                
                row = cursor.fetchone()
                if row:
                    return Program(
                        title=row['title'],
                        start_time=datetime.fromtimestamp(row['start_time']),
                        end_time=datetime.fromtimestamp(row['end_time']),
                        description=row['description']
                    )
            return None
        except sqlite3.Error:
            return None
    
    def get_upcoming_programs(self, channel_id: str, limit: int = 5) -> List[Program]:
        try:
            current_time = int(datetime.now().timestamp())
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT * FROM epg_data 
                    WHERE channel_id = ? 
                    AND end_time > ?
                    ORDER BY start_time
                    LIMIT ?
                ''', (channel_id, current_time, limit))
                
                return [
                    Program(
                        title=row['title'],
                        start_time=datetime.fromtimestamp(row['start_time']),
                        end_time=datetime.fromtimestamp(row['end_time']),
                        description=row['description']
                    )
                    for row in cursor.fetchall()
                ]
        except sqlite3.Error:
            return [] 