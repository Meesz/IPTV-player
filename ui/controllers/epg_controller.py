from PyQt6.QtCore import QObject, pyqtSignal
from core.models import Program
from core.services.epg_service import EPGService

class EPGController(QObject):
    program_updated = pyqtSignal(Program)

    def __init__(self, service: EPGService):
        super().__init__()
        self.service = service

    def load_epg(self, path: str):
        try:
            self.service.load_epg(path)
        except Exception:
            pass # Handle error

    def get_current_program(self, channel_id: str):
        return self.service.get_program_for_channel(channel_id)

    def get_upcoming_programs(self, channel_id: str):
        return self.service.get_upcoming_programs(channel_id)
