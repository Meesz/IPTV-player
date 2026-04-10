from PyQt6.QtCore import QObject, pyqtSignal

from core.models import Channel
from core.services.favorites_service import FavoritesService


class FavoritesController(QObject):
    changed = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, service: FavoritesService):
        super().__init__()
        self.service = service

    def add_favorite(self, channel: Channel) -> bool:
        try:
            result = self.service.add_favorite(channel)
            self.changed.emit()
            return result
        except Exception as exc:
            self.error_occurred.emit(str(exc))
            return False

    def remove_favorite(self, channel: Channel | str) -> bool:
        try:
            url = channel.url if isinstance(channel, Channel) else channel
            result = self.service.remove_favorite(url)
            self.changed.emit()
            return result
        except Exception as exc:
            self.error_occurred.emit(str(exc))
            return False

    def is_favorite(self, channel: Channel | str) -> bool:
        url = channel.url if isinstance(channel, Channel) else channel
        return self.service.is_favorite(url)

    def get_favorites(self) -> list[Channel]:
        return self.service.get_favorites()

    def toggle(self, channel: Channel) -> bool:
        if self.is_favorite(channel):
            return self.remove_favorite(channel)
        return self.add_favorite(channel)
