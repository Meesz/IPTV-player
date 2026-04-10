from PyQt6.QtCore import QObject, pyqtSignal

from core.models import Channel
from core.services.history_service import HistoryService


class HistoryController(QObject):
    changed = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, service: HistoryService):
        super().__init__()
        self.service = service

    def record_channel(self, channel: Channel, playlist_path: str) -> None:
        try:
            self.service.record_channel(channel, playlist_path)
            self.changed.emit()
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    def get_recent_channels(self, limit: int = 12) -> list[Channel]:
        return self.service.get_recent_channels(limit=limit)
