from typing import Any
from core.models import Settings
from infra.db.settings_repository import SettingsRepository

class SettingsService:
    def __init__(self, repository: SettingsRepository):
        self.repository = repository
        self._settings = Settings()
        self.load_settings()

    def load_settings(self):
        self._settings.theme = self.repository.get_setting("theme", "dark")
        self._settings.volume = int(self.repository.get_setting("volume", "100"))
        self._settings.last_playlist_path = self.repository.get_setting("last_playlist", "")
        self._settings.last_channel_url = self.repository.get_setting("last_channel_url", "")
        # ... load other settings

    def get_setting(self, key: str) -> Any:
        return getattr(self._settings, key, None)

    def save_setting(self, key: str, value: Any):
        setattr(self._settings, key, value)
        self.repository.save_setting(key, str(value))

    @property
    def settings(self) -> Settings:
        return self._settings
