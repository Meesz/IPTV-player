from typing import List

from PyQt6.QtCore import QObject, pyqtSignal

from core.errors import NetworkError, ParsingError
from core.models import Program
from core.services.epg_service import EPGService


class EPGController(QObject):
    epg_loaded = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, service: EPGService):
        super().__init__()
        self.service = service

    def load_epg_file(self, path: str) -> bool:
        try:
            self.service.load_epg_from_path(path)
            self.epg_loaded.emit()
            return True
        except (NetworkError, ParsingError, OSError, ValueError) as exc:
            self.error_occurred.emit(str(exc))
            return False

    def load_epg_url(self, url: str) -> bool:
        try:
            self.service.load_epg_from_url(url)
            self.epg_loaded.emit()
            return True
        except (NetworkError, ParsingError, OSError, ValueError) as exc:
            self.error_occurred.emit(str(exc))
            return False

    def get_current_program(self, channel_id: str) -> Program | None:
        if not channel_id:
            return None
        return self.service.get_program_for_channel(channel_id)

    def get_upcoming_programs(self, channel_id: str) -> List[Program]:
        if not channel_id:
            return []
        return self.service.get_upcoming_programs(channel_id)

    @property
    def loaded_channel_count(self) -> int:
        return len(self.service.loaded_channels)
