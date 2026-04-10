from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

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
    last_played_at: Optional[int] = None
    id: Optional[int] = None

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
    path: str
    is_url: bool = False
    channel_count: int = 0
    last_loaded_at: str = ""
    last_status: str = ""
    last_error: str = ""


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
    favorite_keys: Set[tuple[str, str]] = field(default_factory=set)


@dataclass(frozen=True)
class Settings:
    """Application settings."""

    theme: str = "dark"
    volume: int = 100
    is_muted: bool = False
    last_playlist_path: str = ""
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
            last_channel_url=kwargs.get("last_channel_url", self.last_channel_url),
            last_channel_group=kwargs.get("last_channel_group", self.last_channel_group),
            last_epg_path=kwargs.get("last_epg_path", self.last_epg_path),
            last_epg_url=kwargs.get("last_epg_url", self.last_epg_url),
            last_epg_loaded_at=kwargs.get("last_epg_loaded_at", self.last_epg_loaded_at),
            window_width=kwargs.get("window_width", self.window_width),
            window_height=kwargs.get("window_height", self.window_height),
            play_on_single_click=kwargs.get("play_on_single_click", self.play_on_single_click),
            show_now_playing_in_list=kwargs.get(
                "show_now_playing_in_list", self.show_now_playing_in_list
            ),
            search_current_category_only=kwargs.get(
                "search_current_category_only", self.search_current_category_only
            ),
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
    source_hash: str = ""
    channels: List[Channel] = field(default_factory=list)
    parse_warnings: List[ParseWarning] = field(default_factory=list)
    last_updated: Optional[int] = None
    
    # Internal indexes for faster lookups
    _categories: Dict[str, List[Channel]] = field(default_factory=dict)
    _categories_set: Set[str] = field(default_factory=set)
    _url_index: Dict[str, Channel] = field(default_factory=dict)
    _name_index: Dict[str, List[Channel]] = field(default_factory=dict)

    def __post_init__(self):
        self._rebuild_indexes()

    def replace_channels(self, channels: List[Channel]) -> None:
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
    def categories(self) -> List[str]:
        return sorted(self._categories_set)

    def get_channels_by_category(self, category: str) -> List[Channel]:
        return self._categories.get(category, [])

    def get_channel_by_url(self, url: str) -> Optional[Channel]:
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
    programs: List[Program] = field(default_factory=list)

    def get_current_program(self, current_time: Optional[datetime] = None) -> Optional[Program]:
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        elif current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        for program in self.programs:
            if program.start_time <= current_time < program.end_time:
                return program
        return None

    def get_upcoming_programs(self, current_time: Optional[datetime] = None, limit: int = 5) -> List[Program]:
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        elif current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        upcoming = [p for p in self.programs if p.start_time > current_time]
        upcoming.sort(key=lambda p: p.start_time)
        return upcoming[:limit]
