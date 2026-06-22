import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from urllib.parse import urlparse, urlunparse


class PlaylistSourceType(str, Enum):
    FILE = "file"
    URL = "url"
    XTREAM = "xtream"


@dataclass(frozen=True)
class XtreamCredentials:
    """Credentials required for an Xtream-compatible live TV source."""

    server_url: str
    username: str
    password: str
    output: str = "ts"

    @staticmethod
    def normalize_server_url(value: str) -> str:
        raw = value.strip()
        if not raw:
            return ""

        parsed = urlparse(raw)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        if path.endswith("/player_api.php"):
            path = path[: -len("/player_api.php")]
        elif path.endswith("/get.php"):
            path = path[: -len("/get.php")]
        return urlunparse((scheme, netloc, path, "", "", "")).rstrip("/")

    def normalized(self) -> "XtreamCredentials":
        return XtreamCredentials(
            server_url=self.normalize_server_url(self.server_url),
            username=self.username.strip(),
            password=self.password.strip(),
            output=self.output.strip().lower() or "ts",
        )

    def redacted_summary(self) -> str:
        parsed = urlparse(self.normalize_server_url(self.server_url))
        host = parsed.netloc or self.server_url.strip()
        return f"{host} / {self.username.strip()} / {self.output.strip().lower() or 'ts'}"


@dataclass
class Channel:
    """Represents a TV channel with its properties."""

    name: str
    url: str
    group: str = ""
    logo: str = ""
    epg_id: str = ""
    channel_number: int = 0
    time_shift: int = 0
    playlist_path: str = ""
    last_played_at: int | None = None
    id: int | None = None

    def identity_key(self) -> tuple[str, str]:
        return (self.url, self.playlist_path or "")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Channel):
            return False
        return self.identity_key() == other.identity_key()

    def __hash__(self) -> int:
        return hash(self.identity_key())


@dataclass(frozen=True)
class PlaylistReference:
    """Reference metadata for a stored playlist entry."""

    name: str
    path: str = ""
    source_type: PlaylistSourceType = PlaylistSourceType.FILE
    xtream: XtreamCredentials | None = None
    channel_count: int = 0
    last_loaded_at: str = ""
    last_status: str = ""
    last_error: str = ""

    @property
    def is_url(self) -> bool:
        return self.source_type == PlaylistSourceType.URL

    @property
    def source_identity(self) -> str:
        if self.source_type == PlaylistSourceType.FILE:
            return f"file::{self.normalized_path()}"
        if self.source_type == PlaylistSourceType.URL:
            return f"url::{self.normalized_url()}"
        creds = self.normalized_xtream()
        return f"xtream::{creds.server_url}::{creds.username}::{creds.output}"

    def identity_key(self) -> tuple[str, ...]:
        if self.source_type == PlaylistSourceType.XTREAM:
            creds = self.normalized_xtream()
            return (self.source_type.value, creds.server_url, creds.username, creds.output)
        if self.source_type == PlaylistSourceType.URL:
            return (self.source_type.value, self.normalized_url())
        return (self.source_type.value, self.normalized_path())

    def normalized_path(self) -> str:
        raw = self.path.strip()
        if not raw:
            return ""
        return os.path.abspath(raw)

    def normalized_url(self) -> str:
        return self.path.strip()

    def normalized_xtream(self) -> XtreamCredentials:
        return (self.xtream or XtreamCredentials("", "", "", "ts")).normalized()

    def display_label(self) -> str:
        name = self.name.strip() or "Playlist"
        if self.source_type == PlaylistSourceType.XTREAM:
            return name
        if self.source_type == PlaylistSourceType.URL:
            return name
        normalized_path = self.normalized_path() if self.path.strip() else ""
        return name or os.path.basename(normalized_path) or "Playlist"

    def source_summary(self) -> str:
        if self.source_type == PlaylistSourceType.FILE:
            return self.normalized_path()
        if self.source_type == PlaylistSourceType.URL:
            return self.normalized_url()
        return self.normalized_xtream().redacted_summary()

    def to_settings_value(self) -> str:
        payload = {
            "source_type": self.source_type.value,
            "path": (self.normalized_url() if self.source_type == PlaylistSourceType.URL else self.normalized_path()),
            "source_identity": self.source_identity,
        }
        if self.source_type == PlaylistSourceType.XTREAM:
            creds = self.normalized_xtream()
            payload["xtream"] = {
                "server_url": creds.server_url,
                "username": creds.username,
                "output": creds.output,
            }
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)

    @classmethod
    def from_settings_value(cls, value: str) -> "PlaylistReference | None":
        raw = str(value).strip()
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            source_type = PlaylistSourceType.URL if raw.startswith(("http://", "https://")) else PlaylistSourceType.FILE
            return cls(name="Playlist", path=raw, source_type=source_type)

        raw_source_type = str(payload.get("source_type", PlaylistSourceType.FILE.value))
        try:
            source_type = PlaylistSourceType(raw_source_type)
        except ValueError:
            # Degrade gracefully on an unknown/forward-incompatible source_type,
            # mirroring the malformed-JSON branch above, so corrupted settings
            # cannot crash the caller.
            path_value = str(payload.get("path", ""))
            source_type = (
                PlaylistSourceType.URL if path_value.startswith(("http://", "https://")) else PlaylistSourceType.FILE
            )
        xtream_payload = payload.get("xtream")
        xtream = None
        if isinstance(xtream_payload, dict):
            xtream = XtreamCredentials(
                server_url=str(xtream_payload.get("server_url", "")),
                username=str(xtream_payload.get("username", "")),
                password="",
                output=str(xtream_payload.get("output", "ts")),
            )
        return cls(
            name=str(payload.get("name", "Playlist")),
            path=str(payload.get("path", "")),
            source_type=source_type,
            xtream=xtream,
        )


@dataclass(frozen=True)
class ParseWarning:
    """Represents a non-fatal parser warning."""

    code: str
    message: str
    context: str = ""


@dataclass(frozen=True)
class ChannelQuery:
    """Canonical channel filtering and sorting input."""

    category: str = "All"
    text: str = ""
    current_category_only: bool = True
    sort_mode: str = "name_asc"
    favorite_keys: set[tuple[str, str]] = field(default_factory=set)


@dataclass(frozen=True)
class Settings:
    """Application settings."""

    theme: str = "dark"
    volume: int = 100
    is_muted: bool = False
    last_playlist_path: str = ""
    last_playlist_source_type: str = PlaylistSourceType.FILE.value
    last_playlist_identity: str = ""
    last_channel_url: str = ""
    last_channel_group: str = ""
    last_epg_path: str = ""
    last_epg_url: str = ""
    last_epg_loaded_at: str = ""
    window_width: int = 1280
    window_height: int = 720
    play_on_single_click: bool = False
    show_now_playing_in_list: bool = True
    search_current_category_only: bool = True
    channel_sort_mode: str = "name_asc"
    splitter_sizes: tuple[int, int] = (390, 960)
    active_tab_index: int = 0
    selected_category: str = "All"
    search_text: str = ""
    left_panel_visible: bool = True

    @classmethod
    def defaults(cls) -> "Settings":
        return cls()

    def with_updates(self, **kwargs: object) -> "Settings":
        return type(self)(
            theme=kwargs.get("theme", self.theme),
            volume=kwargs.get("volume", self.volume),
            is_muted=kwargs.get("is_muted", self.is_muted),
            last_playlist_path=kwargs.get("last_playlist_path", self.last_playlist_path),
            last_playlist_source_type=kwargs.get("last_playlist_source_type", self.last_playlist_source_type),
            last_playlist_identity=kwargs.get("last_playlist_identity", self.last_playlist_identity),
            last_channel_url=kwargs.get("last_channel_url", self.last_channel_url),
            last_channel_group=kwargs.get("last_channel_group", self.last_channel_group),
            last_epg_path=kwargs.get("last_epg_path", self.last_epg_path),
            last_epg_url=kwargs.get("last_epg_url", self.last_epg_url),
            last_epg_loaded_at=kwargs.get("last_epg_loaded_at", self.last_epg_loaded_at),
            window_width=kwargs.get("window_width", self.window_width),
            window_height=kwargs.get("window_height", self.window_height),
            play_on_single_click=kwargs.get("play_on_single_click", self.play_on_single_click),
            show_now_playing_in_list=kwargs.get("show_now_playing_in_list", self.show_now_playing_in_list),
            search_current_category_only=kwargs.get("search_current_category_only", self.search_current_category_only),
            channel_sort_mode=kwargs.get("channel_sort_mode", self.channel_sort_mode),
            splitter_sizes=kwargs.get("splitter_sizes", self.splitter_sizes),
            active_tab_index=kwargs.get("active_tab_index", self.active_tab_index),
            selected_category=kwargs.get("selected_category", self.selected_category),
            search_text=kwargs.get("search_text", self.search_text),
            left_panel_visible=kwargs.get("left_panel_visible", self.left_panel_visible),
        )


@dataclass
class Playlist:
    """Represents a collection of channels from an M3U/M3U8 playlist."""

    name: str = "Unnamed Playlist"
    source_path: str = ""
    source_reference: PlaylistReference | None = None
    source_hash: str = ""
    channels: list[Channel] = field(default_factory=list)
    parse_warnings: list[ParseWarning] = field(default_factory=list)
    last_updated: int | None = None

    # Internal indexes for faster lookups
    _categories: dict[str, list[Channel]] = field(default_factory=dict)
    _categories_set: set[str] = field(default_factory=set)
    _url_index: dict[str, Channel] = field(default_factory=dict)
    _name_index: dict[str, list[Channel]] = field(default_factory=dict)

    def __post_init__(self):
        self._rebuild_indexes()

    def replace_channels(self, channels: list[Channel]) -> None:
        self.channels = channels
        self._rebuild_indexes()

    def add_channel(self, channel: Channel) -> None:
        self.channels.append(channel)
        self._update_indexes(channel)

    def _update_indexes(self, channel: Channel) -> None:
        category = channel.group or "Uncategorized"
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(channel)
        self._categories_set.add(category)

        self._url_index[channel.url] = channel

        if channel.name not in self._name_index:
            self._name_index[channel.name] = []
        self._name_index[channel.name].append(channel)

    def _rebuild_indexes(self) -> None:
        self._categories.clear()
        self._categories_set.clear()
        self._url_index.clear()
        self._name_index.clear()
        for channel in self.channels:
            self._update_indexes(channel)

    @property
    def categories(self) -> list[str]:
        return sorted(self._categories_set)

    def get_channels_by_category(self, category: str) -> list[Channel]:
        return self._categories.get(category, [])

    def get_channel_by_url(self, url: str) -> Channel | None:
        return self._url_index.get(url)


@dataclass
class Program:
    """Represents a TV program with its details."""

    title: str
    start_time: datetime
    end_time: datetime
    description: str = ""
    category: str = ""

    @property
    def duration_minutes(self) -> int:
        return int((self.end_time - self.start_time).total_seconds() / 60)


@dataclass
class EPGChannel:
    """Holds EPG data for a specific channel."""

    channel_id: str
    programs: list[Program] = field(default_factory=list)

    def get_current_program(self, current_time: datetime | None = None) -> Program | None:
        if current_time is None:
            current_time = datetime.now(UTC)
        elif current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)
        for program in self.programs:
            if program.start_time <= current_time < program.end_time:
                return program
        return None

    def get_upcoming_programs(self, current_time: datetime | None = None, limit: int = 5) -> list[Program]:
        if current_time is None:
            current_time = datetime.now(UTC)
        elif current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)
        upcoming = [p for p in self.programs if p.start_time > current_time]
        upcoming.sort(key=lambda p: p.start_time)
        return upcoming[:limit]
