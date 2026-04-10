from typing import Any

from core.errors import RepositoryError
from core.models import Settings
from infra.db.settings_repository import SettingsRepository


class SettingsService:
    def __init__(self, repository: SettingsRepository):
        self.repository = repository
        self._settings = Settings.defaults()
        self._load_settings()

    def _load_settings(self) -> None:
        try:
            self._settings = Settings(
                theme=self.repository.get_setting("theme", self._settings.theme),
                volume=int(self.repository.get_setting("volume", str(self._settings.volume))),
                is_muted=self._to_bool(self.repository.get_setting("is_muted", "false")),
                last_playlist_path=self.repository.get_setting(
                    "last_playlist_path",
                    self.repository.get_setting(
                        "last_playlist", self._settings.last_playlist_path
                    ),
                ),
                last_channel_url=self.repository.get_setting(
                    "last_channel_url", self._settings.last_channel_url
                ),
                last_epg_path=self.repository.get_setting(
                    "last_epg_path",
                    self.repository.get_setting(
                        "last_epg_file", self._settings.last_epg_path
                    ),
                ),
                last_epg_url=self.repository.get_setting(
                    "last_epg_url", self.repository.get_setting("epg_url", "")
                ),
                window_width=int(
                    self.repository.get_setting(
                        "window_width", str(self._settings.window_width)
                    )
                ),
                window_height=int(
                    self.repository.get_setting(
                        "window_height", str(self._settings.window_height)
                    )
                ),
            )
        except RepositoryError:
            self._settings = Settings.defaults()
        except ValueError:
            self._settings = Settings.defaults()

        # Backward compatibility migration: keep both legacy and new keys in sync.
        try:
            self._persist_legacy_compatibility_settings()
        except RepositoryError:
            pass

    def _persist_legacy_compatibility_settings(self) -> None:
        self.repository.save_setting("last_playlist", self._settings.last_playlist_path)
        self.repository.save_setting("last_epg_file", self._settings.last_epg_path)
        self.repository.save_setting("epg_url", self._settings.last_epg_url)
        playlist_is_url = self.repository.get_setting("last_playlist_is_url", "false")
        normalized_value = str(playlist_is_url).strip().lower()
        is_recognized_bool = normalized_value in {"0", "1", "true", "false", "yes", "no", "on", "off"}
        if not is_recognized_bool:
            playlist_is_url = (
                "true" if self._settings.last_playlist_path.startswith(("http://", "https://")) else "false"
            )
        self.repository.save_setting("last_playlist_is_url", playlist_is_url)

    @staticmethod
    def _to_bool(value: str) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def get_setting(self, key: str, default: Any = None) -> Any:
        if not hasattr(self._settings, key):
            return default
        return getattr(self._settings, key)

    def save_setting(self, key: str, value: Any) -> None:
        self.repository.save_setting(key, str(value))
        if hasattr(self._settings, key):
            self._settings = self._settings.with_updates(**{key: value})

        normalized_key = key
        if isinstance(value, bool):
            normalized_value = "true" if value else "false"
        else:
            normalized_value = str(value)

        if normalized_key == "last_playlist_path":
            self._settings = self._settings.with_updates(last_playlist_path=normalized_value)
            self.repository.save_setting("last_playlist", normalized_value)
            self.repository.save_setting(
                "last_playlist_is_url",
                "true" if str(value).startswith(("http://", "https://")) else "false",
            )
        elif normalized_key == "last_playlist":
            self._settings = self._settings.with_updates(last_playlist_path=normalized_value)
            self.repository.save_setting("last_playlist_path", normalized_value)
            self.repository.save_setting(
                "last_playlist_is_url",
                "true" if str(value).startswith(("http://", "https://")) else "false",
            )
        elif normalized_key == "last_epg_path":
            self.repository.save_setting("last_epg_file", normalized_value)
        elif normalized_key in {"epg_url", "last_epg_url"}:
            self._settings = self._settings.with_updates(last_epg_url=normalized_value)
            self.repository.save_setting("epg_url", normalized_value)
            self.repository.save_setting("last_epg_url", normalized_value)

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def typed(self) -> Settings:
        return self._settings
