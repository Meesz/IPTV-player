import sqlite3
from pathlib import Path
from typing import List, Optional
from models.playlist import Channel
from models.epg import Program
from datetime import datetime

class Database:
    def __init__(self):
        self.db_path = Path.home() / '.simple_iptv' / 'database.db'
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Database path: {self.db_path}")
        self._connection = None
        self.init_database()
    
    def _get_connection(self):
        """Get a new connection if none exists"""
        if self._connection is None:
            self._connection = sqlite3.connect(str(self.db_path))  # Ensure path is string
            self._connection.row_factory = sqlite3.Row
        return self._connection
    
    def close(self):
        if self._connection:
            self._connection.close()
            self._connection = None
    
    def init_database(self):
        conn = None
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            
            # Enable WAL mode for better performance
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA cache_size=-2000')
            conn.execute('PRAGMA temp_store=MEMORY')
            
            # Create tables
            conn.executescript('''
                -- Create playlists table if not exists (don't drop it!)
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    is_url BOOLEAN NOT NULL DEFAULT 0
                );
                
                -- Create settings table if not exists
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                
                -- Create EPG table if not exists
                CREATE TABLE IF NOT EXISTS epg_data (
                    channel_id TEXT,
                    start_time INTEGER,
                    end_time INTEGER,
                    title TEXT,
                    description TEXT,
                    PRIMARY KEY (channel_id, start_time)
                );
                
                -- Create favorites table if not exists
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    group_name TEXT,
                    logo TEXT,
                    epg_id TEXT
                );
                
                -- Add default settings
                INSERT OR IGNORE INTO settings (key, value) VALUES ('last_playlist', '');
                INSERT OR IGNORE INTO settings (key, value) VALUES ('last_epg_file', '');
                INSERT OR IGNORE INTO settings (key, value) VALUES ('epg_url', '');
                INSERT OR IGNORE INTO settings (key, value) VALUES ('last_playlist_is_url', 'false');
            ''')
            
            conn.commit()
            print("Database initialized successfully")
            
            # Debug print table contents
            cursor = conn.execute('SELECT COUNT(*) FROM playlists')
            count = cursor.fetchone()[0]
            print(f"Found {count} existing playlists in database")
            
            if count > 0:
                cursor = conn.execute('SELECT name, path, is_url FROM playlists')
                for row in cursor:
                    print(f"Existing playlist: {row['name']}, {row['path']}, {bool(row['is_url'])}")
            
        except sqlite3.Error as e:
            print(f"Error initializing database: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
    
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
    
    def save_playlists(self, playlists):
        """Save list of (name, path, is_url) tuples"""
        conn = None
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            
            # Start transaction
            conn.execute('BEGIN')
            
            # Debug print current playlists before deletion
            cursor = conn.execute('SELECT COUNT(*) FROM playlists')
            count = cursor.fetchone()[0]
            print(f"Current playlists in DB before deletion: {count}")
            
            # Clear existing playlists
            conn.execute('DELETE FROM playlists')
            
            # Insert new playlists
            for name, path, is_url in playlists:
                print(f"Saving playlist: {name}, {path}, {is_url}")  # Debug print
                conn.execute(
                    'INSERT INTO playlists (name, path, is_url) VALUES (?, ?, ?)',
                    (name, path, 1 if is_url else 0)
                )
            
            # Commit changes
            conn.commit()
            
            # Verify the save
            cursor = conn.execute('SELECT COUNT(*) FROM playlists')
            count = cursor.fetchone()[0]
            print(f"Playlists in DB after save: {count}")
            
            return True
            
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            print(f"Error saving playlists: {e}")
            return False
            
        finally:
            if conn:
                conn.close()
    
    def get_playlists(self):
        """Add index on frequently queried columns"""
        conn = None
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            
            # Debug print table info
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='playlists'")
            if not cursor.fetchone():
                print("Playlists table does not exist!")
                return []
            
            cursor = conn.execute('SELECT name, path, is_url FROM playlists')
            rows = cursor.fetchall()
            playlists = [(row['name'], row['path'], bool(row['is_url'])) for row in rows]
            
            print(f"Loaded {len(playlists)} playlists from database")
            for name, path, is_url in playlists:
                print(f"Loaded playlist: {name}, {path}, {is_url}")  # Debug print
            
            return playlists
            
        except sqlite3.Error as e:
            print(f"Error loading playlists: {e}")
            return []
            
        finally:
            if conn:
                conn.close() 