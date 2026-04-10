import logging
from datetime import datetime
from typing import Dict, List, Optional

from core.errors import RepositoryError
from core.models import Program
from infra.db.sqlite_connection import SQLiteConnection

logger = logging.getLogger(__name__)


class EPGRepository:
    def __init__(self, db: SQLiteConnection):
        self.db = db

    def save_program(self, channel_id: str, program: Program) -> None:
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
        except Exception as exc:
            logger.error("Failed to save program for channel %s: %s", channel_id, exc)
            raise RepositoryError("Failed to save EPG program") from exc

    def save_all(self, programs_by_channel: Dict[str, List[Program]]) -> None:
        try:
            with self.db.get_connection() as conn:
                conn.execute("DELETE FROM epg_data")
                for channel_id, programs in programs_by_channel.items():
                    for program in programs:
                        conn.execute(
                            """
                            INSERT INTO epg_data
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
        except Exception as exc:
            logger.error("Failed to save EPG cache: %s", exc)
            raise RepositoryError("Failed to persist EPG cache") from exc

    def clear(self) -> None:
        try:
            with self.db.get_connection() as conn:
                conn.execute("DELETE FROM epg_data")
        except Exception as exc:
            logger.error("Failed to clear EPG data: %s", exc)
            raise RepositoryError("Failed to clear EPG cache") from exc

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
                    ORDER BY start_time
                    LIMIT 1
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
        except Exception as exc:
            logger.error(
                "Failed to get current program for channel %s: %s",
                channel_id,
                exc,
            )
            raise RepositoryError("Failed to query current EPG program") from exc

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
        except Exception as exc:
            logger.error(
                "Failed to get upcoming programs for channel %s: %s",
                channel_id,
                exc,
            )
            raise RepositoryError("Failed to query upcoming EPG programs") from exc
