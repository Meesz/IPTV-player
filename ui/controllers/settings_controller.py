from PyQt6.QtCore import QObject

from core.models import PlaylistReference, PlaylistSourceType
from core.services.settings_service import SettingsService


class SettingsController(QObject):
    def __init__(self, settings_service: SettingsService):
        super().__init__()
        self.service = settings_service

    def get_setting(self, key: str, default=None):
        val = self.service.get_setting(key)
        return val if val is not None else default

    def save_settings(self, settings: dict[str, object]) -> None:
        for key, value in settings.items():
            self.service.save_setting(key, value)

    def save_setting(self, key: str, value):
        self.service.save_setting(key, value)

    def save_active_playlist(self, reference: PlaylistReference) -> None:
        """Persist the active playlist as the restart target.

        Saving ``last_playlist_path`` recomputes identity and source type, so it is
        written first and the authoritative keys last.
        """
        is_xtream = reference.source_type == PlaylistSourceType.XTREAM
        path = "" if is_xtream else reference.path
        self.save_settings(
            {
                "last_playlist_path": path,
                "last_playlist_source_type": reference.source_type.value,
                "last_playlist_identity": reference.source_identity,
            }
        )

    @property
    def settings(self):
        return self.service.settings
