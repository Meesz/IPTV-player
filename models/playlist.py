"""
This module contains the Playlist class for managing IPTV playlists.
"""

from dataclasses import dataclass, field
from typing import List, Set, Dict
from collections import defaultdict
from models.channel import Channel
from utils.m3u_parser import M3UParser
import requests
import tempfile
import os


@dataclass
class Playlist:
    """Represents a collection of channels organized into categories."""

    channels: List[Channel] = field(default_factory=list)
    _categories: Set[str] = field(default_factory=set)
    _url_index: Dict[str, Channel] = field(default_factory=dict)
    _name_index: Dict[str, List[Channel]] = field(default_factory=lambda: defaultdict(list))

    @classmethod
    def from_path(cls, path: str, is_url: bool = False) -> 'Playlist':
        """Create a Playlist instance from a file path or URL."""
        try:
            # Create new playlist instance
            playlist = cls()
            
            if is_url:
                # Handle URL loading (implement URL loading logic)
                response = requests.get(path, timeout=30)
                response.raise_for_status()
                
                # Save content to temporary file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.m3u8', delete=False) as tmp:
                    tmp.write(response.text)
                    tmp_path = tmp.name
                
                # Parse the temporary file
                channels = M3UParser.parse(tmp_path)
                os.unlink(tmp_path)  # Clean up temp file
            else:
                # Parse local file
                channels = M3UParser.parse(path)
            
            # Add all channels to playlist
            for channel in channels:
                playlist.add_channel(channel)
            
            return playlist
            
        except Exception as e:
            raise ValueError(f"Failed to load playlist: {str(e)}") from e

    def add_channel(self, channel: Channel) -> None:
        """Add a channel to the playlist and update categories."""
        self.channels.append(channel)
        if channel.group:
            self._categories.add(channel.group)

        # Update indexes
        self._url_index[channel.url] = channel
        self._name_index[channel.name.lower()].append(channel)

    def clear(self) -> None:
        """Clear all channels and categories."""
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
        """Get sorted list of all categories."""
        return sorted(self._categories)

    def get_channels_by_category(self, category: str) -> List[Channel]:
        """Get all channels in a specific category."""
        return [ch for ch in self.channels if ch.group == category]
