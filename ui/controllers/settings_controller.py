from PyQt6.QtCore import QObject
from core.services.settings_service import SettingsService

class SettingsController(QObject):
    def __init__(self, settings_service: SettingsService):
        super().__init__()
        self.service = settings_service

    def get_setting(self, key: str, default=None):
        val = self.service.get_setting(key)
        return val if val is not None else default

    def save_setting(self, key: str, value):
        self.service.save_setting(key, value)

    @property
    def settings(self):
        return self.service.settings
