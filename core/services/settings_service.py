from typing import Any

from core.errors import RepositoryError
from core.models import PlaylistReference, PlaylistSourceType, Settings
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
                last_playlist_source_type=self.repository.get_setting(
                    "last_playlist_source_type", self._settings.last_playlist_source_type
                ),
                last_playlist_identity=self.repository.get_setting(
                    "last_playlist_identity", self._settings.last_playlist_identity
                ),
                last_channel_url=self.repository.get_setting(
                    "last_channel_url", self._settings.last_channel_url
                ),
                last_channel_group=self.repository.get_setting(
                    "last_channel_group", self._settings.last_channel_group
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
                last_epg_loaded_at=self.repository.get_setting(
                    "last_epg_loaded_at", self._settings.last_epg_loaded_at
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
                play_on_single_click=self._to_bool(
                    self.repository.get_setting("play_on_single_click", "false")
                ),
                show_now_playing_in_list=self._to_bool(
                    self.repository.get_setting("show_now_playing_in_list", "true")
                ),
                search_current_category_only=self._to_bool(
                    self.repository.get_setting("search_current_category_only", "true")
                ),
                channel_sort_mode=self.repository.get_setting(
                    "channel_sort_mode", self._settings.channel_sort_mode
                ),
                splitter_sizes=self._parse_splitter_sizes(
                    self.repository.get_setting("splitter_sizes", "")
                ),
                active_tab_index=int(
                    self.repository.get_setting(
                        "active_tab_index", str(self._settings.active_tab_index)
                    )
                ),
                selected_category=self.repository.get_setting(
                    "selected_category", self._settings.selected_category
                ),
                search_text=self.repository.get_setting(
                    "search_text", self._settings.search_text
                ),
                left_panel_visible=self._to_bool(
                    self.repository.get_setting("left_panel_visible", "true")
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
        self.repository.save_setting(
            "last_playlist_source_type", self._settings.last_playlist_source_type
        )
        self.repository.save_setting(
            "last_playlist_identity", self._settings.last_playlist_identity
        )
        playlist_is_url = self.repository.get_setting("last_playlist_is_url", "false")
        normalized_value = str(playlist_is_url).strip().lower()
        is_recognized_bool = normalized_value in {"0", "1", "true", "false", "yes", "no", "on", "off"}
        if not is_recognized_bool:
            playlist_is_url = (
                "true" if self._settings.last_playlist_source_type == PlaylistSourceType.URL.value else "false"
            )
        self.repository.save_setting("last_playlist_is_url", playlist_is_url)

    @staticmethod
    def _to_bool(value: str) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _parse_splitter_sizes(value: str) -> tuple[int, int]:
        raw = str(value).strip()
        if not raw:
            return Settings.defaults().splitter_sizes

        parts = [part.strip() for part in raw.split(",") if part.strip()]
        if len(parts) != 2:
            return Settings.defaults().splitter_sizes

        first, second = (int(parts[0]), int(parts[1]))
        if first <= 0 or second <= 0:
            return Settings.defaults().splitter_sizes
        return (first, second)

    def get_setting(self, key: str, default: Any = None) -> Any:
        if not hasattr(self._settings, key):
            return default
        return getattr(self._settings, key)

    def save_setting(self, key: str, value: Any) -> None:
        serialized_value = self._serialize_value(key, value)
        self.repository.save_setting(key, serialized_value)
        if hasattr(self._settings, key):
            self._settings = self._settings.with_updates(**{key: value})

        normalized_key = key
        if isinstance(value, bool):
            normalized_value = "true" if value else "false"
        elif key == "splitter_sizes" and isinstance(value, tuple):
            normalized_value = ",".join(str(part) for part in value)
        else:
            normalized_value = str(value)

        if normalized_key == "last_playlist_path":
            source_type = (
                PlaylistSourceType.URL
                if str(value).startswith(("http://", "https://"))
                else PlaylistSourceType.FILE
            )
            source_identity = PlaylistReference(
                name="Playlist",
                path=normalized_value,
                source_type=source_type,
            ).source_identity
            self._settings = self._settings.with_updates(
                last_playlist_path=normalized_value,
                last_playlist_source_type=source_type.value,
                last_playlist_identity=source_identity,
            )
            self.repository.save_setting("last_playlist", normalized_value)
            self.repository.save_setting(
                "last_playlist_is_url",
                "true" if str(value).startswith(("http://", "https://")) else "false",
            )
            self.repository.save_setting(
                "last_playlist_identity",
                source_identity,
            )
            self.repository.save_setting(
                "last_playlist_source_type",
                source_type.value,
            )
        elif normalized_key == "last_playlist":
            source_type = (
                PlaylistSourceType.URL
                if str(value).startswith(("http://", "https://"))
                else PlaylistSourceType.FILE
            )
            source_identity = PlaylistReference(
                name="Playlist",
                path=normalized_value,
                source_type=source_type,
            ).source_identity
            self._settings = self._settings.with_updates(
                last_playlist_path=normalized_value,
                last_playlist_source_type=source_type.value,
                last_playlist_identity=source_identity,
            )
            self.repository.save_setting("last_playlist_path", normalized_value)
            self.repository.save_setting(
                "last_playlist_is_url",
                "true" if str(value).startswith(("http://", "https://")) else "false",
            )
            self.repository.save_setting(
                "last_playlist_identity",
                source_identity,
            )
            self.repository.save_setting(
                "last_playlist_source_type",
                source_type.value,
            )
        elif normalized_key == "last_playlist_source_type":
            self._settings = self._settings.with_updates(
                last_playlist_source_type=normalized_value
            )
        elif normalized_key == "last_playlist_identity":
            self._settings = self._settings.with_updates(last_playlist_identity=normalized_value)
        elif normalized_key == "last_epg_path":
            self._settings = self._settings.with_updates(last_epg_path=normalized_value)
            self.repository.save_setting("last_epg_file", normalized_value)
        elif normalized_key in {"epg_url", "last_epg_url"}:
            self._settings = self._settings.with_updates(last_epg_url=normalized_value)
            self.repository.save_setting("epg_url", normalized_value)
            self.repository.save_setting("last_epg_url", normalized_value)

    @staticmethod
    def _serialize_value(key: str, value: Any) -> str:
        if key == "splitter_sizes":
            if isinstance(value, (tuple, list)):
                return ",".join(str(part) for part in value)
            return str(value)
        return str(value)

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def typed(self) -> Settings:
        return self._settings
