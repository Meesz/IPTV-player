from datetime import datetime

from core.models import Channel
from infra.db.history_repository import HistoryRepository


class HistoryService:
    def __init__(self, repository: HistoryRepository):
        self.repository = repository

    def record_channel(self, channel: Channel, playlist_path: str) -> None:
        played_at = int(datetime.now().timestamp())
        self.repository.record_channel(channel, playlist_path, played_at)

    def get_recent_channels(self, limit: int = 12) -> list[Channel]:
        return self.repository.get_recent_channels(limit=limit)

    def get_last_played_at(self) -> datetime | None:
        return self.repository.get_last_played_at()
