"""
This module defines the playlist data model for the IPTV player.
It includes classes for representing channels and playlists.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Any


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
    id: Optional[int] = None

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Channel":
        """Create a Channel object from a database row.

        Args:
            row: A dictionary-like object with channel attributes.

        Returns:
            Channel: A new Channel instance.
        """
        return cls(
            name=row["name"],
            url=row["url"],
            group=row.get("group_name", ""),
            logo=row.get("logo", ""),
            epg_id=row.get("epg_id", ""),
            channel_number=row.get("channel_number", 0),
            time_shift=row.get("time_shift", 0),
            id=row.get("id", None)
        )

    def __eq__(self, other):
        """Check if two channels are equal based on their URL."""
        if not isinstance(other, Channel):
            return False
        return self.url == other.url

    def __hash__(self):
        """Return a hash of the channel based on its URL."""
        return hash(self.url)


class Playlist:
    """Represents a collection of channels from an M3U/M3U8 playlist."""

    def __init__(self):
        """Initialize an empty playlist."""
        self.channels: List[Channel] = []
        self._categories: Dict[str, List[Channel]] = {}
        self._categories_set: Set[str] = set()
        self._url_index: Dict[str, Channel] = {}
        self._name_index: Dict[str, List[Channel]] = {}
        self.source_path: str = ""
        self.source_hash: str = ""
        self.name: str = "Unnamed Playlist"
        self.last_updated: Optional[int] = None

    def add_channel(self, channel: Channel) -> None:
        """Add a channel to the playlist.

        Args:
            channel: The channel to add.
        """
        self.channels.append(channel)
        
        # Update category index
        category = channel.group or "Uncategorized"
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(channel)
        self._categories_set.add(category)
        
        # Update URL index
        self._url_index[channel.url] = channel
        
        # Update name index
        if channel.name not in self._name_index:
            self._name_index[channel.name] = []
        self._name_index[channel.name].append(channel)

    def get_channel_by_url(self, url: str) -> Optional[Channel]:
        """Get a channel by its URL.

        Args:
            url: The URL to search for.

        Returns:
            The channel with the specified URL, or None if not found.
        """
        return self._url_index.get(url)

    def get_channels_by_name(self, name: str) -> List[Channel]:
        """Get all channels with the given name.

        Args:
            name: The name to search for.

        Returns:
            A list of channels with the specified name.
        """
        return self._name_index.get(name, [])

    @property
    def categories(self) -> List[str]:
        """Get a sorted list of all categories in the playlist.

        Returns:
            A sorted list of category names.
        """
        return sorted(self._categories_set)

    def get_channels_by_category(self, category: str) -> List[Channel]:
        """Get all channels belonging to a specific category.

        Args:
            category: The category to filter by.

        Returns:
            A list of channels in the specified category.
        """
        return self._categories.get(category, [])

    def search_channels(self, query: str) -> List[Channel]:
        """Search for channels by name.

        Args:
            query: The search query string.

        Returns:
            A list of channels matching the search criteria.
        """
        query = query.lower()
        return [
            channel for channel in self.channels if query in channel.name.lower()
        ]

    def sort_channels(self, key: str = "name", reverse: bool = False) -> None:
        """Sort channels by the specified key.

        Args:
            key: The attribute to sort by ('name', 'group', 'channel_number').
            reverse: True for descending order, False for ascending.
        """
        if key == "channel_number" and any(c.channel_number > 0 for c in self.channels):
            # Sort by channel number and then by name for those without channel numbers
            self.channels.sort(
                key=lambda x: (x.channel_number == 0, x.channel_number, x.name.lower()),
                reverse=reverse
            )
        else:
            # Sort by the specified attribute
            self.channels.sort(
                key=lambda x: getattr(x, key, "").lower() if isinstance(getattr(x, key, ""), str) else getattr(x, key, 0),
                reverse=reverse
            )
            
        # Rebuild indexes after sorting
        self._rebuild_indexes()
        
    def _rebuild_indexes(self) -> None:
        """Rebuild internal indexes after channel list changes."""
        self._categories.clear()
        self._categories_set.clear()
        self._url_index.clear()
        self._name_index.clear()
        
        # Rebuild all indexes
        for channel in self.channels:
            category = channel.group or "Uncategorized"
            if category not in self._categories:
                self._categories[category] = []
            self._categories[category].append(channel)
            self._categories_set.add(category)
            
            self._url_index[channel.url] = channel
            
            if channel.name not in self._name_index:
                self._name_index[channel.name] = []
            self._name_index[channel.name].append(channel)

    def clear(self) -> None:
        """Clear the playlist."""
        self.channels = []
        self._categories.clear()
        self._categories_set.clear()
        self._url_index.clear()
        self._name_index.clear()

    def merge(self, other_playlist: "Playlist") -> None:
        """Merge another playlist into this one.
        
        Args:
            other_playlist: The playlist to merge with this one.
        """
        for channel in other_playlist.channels:
            self.add_channel(channel)
            
    def get_channel_by_epg_id(self, epg_id: str) -> Optional[Channel]:
        """Find a channel by its EPG ID.
        
        Args:
            epg_id: The EPG ID to search for.
            
        Returns:
            The channel with the specified EPG ID, or None if not found.
        """
        if not epg_id:
            return None
            
        for channel in self.channels:
            if channel.epg_id == epg_id:
                return channel
        return None
        
    @property
    def has_channel_numbers(self) -> bool:
        """Check if any channels in the playlist have channel numbers.
        
        Returns:
            True if any channel has a channel number greater than 0.
        """
        return any(channel.channel_number > 0 for channel in self.channels)
