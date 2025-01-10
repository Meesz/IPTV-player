"""
This module contains the Playlist class, which manages a collection of TV channels.
"""

from dataclasses import dataclass
from typing import List, Dict
from collections import defaultdict


@dataclass
class Channel:
    """Represents a TV channel with its associated metadata."""

    name: str
    url: str
    group: str = ""
    logo: str = ""
    epg_id: str = ""
    id: int = None

    def __hash__(self):
        """Generate a hash based on the channel's URL."""
        return hash(self.url)  # Use URL as unique identifier

    @staticmethod
    def from_db_row(row):
        """Create a Channel instance from a database row.

        Args:
            row (dict): A dictionary representing a database row with channel data.

        Returns:
            Channel: An instance of the Channel class.
        """
        return Channel(
            name=row["name"],
            url=row["url"],
            group=row["group_name"],
            logo=row["logo"],
            epg_id=row["epg_id"],
            id=row["id"],
        )


class Playlist:
    """Manages a collection of TV channels and provides methods to interact with them."""

    def __init__(self):
        """Initialize the Playlist with empty data structures for channels and indexes."""
        self.channels: List[Channel] = []
        self._categories: Dict[str, List[Channel]] = defaultdict(list)
        self._url_index: Dict[str, Channel] = {}  # Index for quick URL lookups
        self._name_index: Dict[str, List[Channel]] = defaultdict(
            list
        )  # Index for quick name searches

    def add_channel(self, channel: Channel):
        """Add a channel to the playlist and update indexes.

        Args:
            channel (Channel): The channel to add.
        """
        self.channels.append(channel)
        category = channel.group or "Uncategorized"
        self._categories[category].append(channel)

        # Update indexes
        self._url_index[channel.url] = channel
        self._name_index[channel.name.lower()].append(channel)

    def clear(self):
        """Clear all channels and indexes from the playlist."""
        self.channels.clear()
        self._categories.clear()
        self._url_index.clear()
        self._name_index.clear()

    def get_channel_by_url(self, url: str) -> Channel:
        """Retrieve a channel by its URL.

        Args:
            url (str): The URL of the channel.

        Returns:
            Channel: The channel with the specified URL, or None if not found.
        """
        return self._url_index.get(url)
    def search_channels(self, query: str) -> List[Channel]:
        """Search for channels by name.

        Args:
            query (str): The search query string.

        Returns:
            List[Channel]: A list of channels whose names match the query.
        """
        query = query.lower()
        return [
            channel
            for name, channels in self._name_index.items()
            if query in name
            for channel in channels
        ]

    @property
    def categories(self) -> List[str]:
        """Get a sorted list of channel categories.

        Returns:
            List[str]: A list of category names.
        """
        return sorted(self._categories.keys())

    def get_channels_by_category(self, category: str) -> List[Channel]:
        """Retrieve channels by category.

        Args:
            category (str): The category name.

        Returns:
            List[Channel]: A list of channels in the specified category.
        """
        return self._categories.get(category, [])
