from typing import List, Optional
from datetime import datetime
from infra.db.sqlite_connection import SQLiteConnection
from core.models import Program

class EPGRepository:
    def __init__(self, db: SQLiteConnection):
        self.db = db

    def save_program(self, channel_id: str, program: Program) -> bool:
        try:
            with self.db.get_connection() as conn:
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
        except Exception:
            return False

    def get_current_program(self, channel_id: str) -> Optional[Program]:
        try:
            current_time = int(datetime.now().timestamp())
            with self.db.get_connection() as conn:
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
        except Exception:
            return None

    def get_upcoming_programs(self, channel_id: str, limit: int = 5) -> List[Program]:
        try:
            current_time = int(datetime.now().timestamp())
            with self.db.get_connection() as conn:
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
        except Exception:
            return []
