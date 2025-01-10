from dataclasses import dataclass
from typing import List, Dict
from collections import defaultdict

@dataclass
class Channel:
    name: str
    url: str
    group: str = ""
    logo: str = ""
    epg_id: str = ""
    id: int = None

    def __hash__(self):
        return hash(self.url)  # Use URL as unique identifier

    @staticmethod
    def from_db_row(row):
        """Create a Channel instance from a database row."""
        return Channel(
            name=row['name'],
            url=row['url'],
            group=row['group_name'],
            logo=row['logo'],
            epg_id=row['epg_id'],
            id=row['id']
        )

class Playlist:
    def __init__(self):
        self.channels: List[Channel] = []
        self._categories: Dict[str, List[Channel]] = defaultdict(list)
        self._url_index: Dict[str, Channel] = {}  # Index for quick URL lookups
        self._name_index: Dict[str, List[Channel]] = defaultdict(list)  # Index for quick name searches
    
    def add_channel(self, channel: Channel):
        self.channels.append(channel)
        category = channel.group or "Uncategorized"
        self._categories[category].append(channel)
        
        # Update indexes
        self._url_index[channel.url] = channel
        self._name_index[channel.name.lower()].append(channel)
    
    def clear(self):
        self.channels.clear()
        self._categories.clear()
        self._url_index.clear()
        self._name_index.clear()
    
    def get_channel_by_url(self, url: str) -> Channel:
        return self._url_index.get(url)
    
    def search_channels(self, query: str) -> List[Channel]:
        query = query.lower()
        return [
            channel for name_match in self._name_index.keys()
            if query in name_match
            for channel in self._name_index[name_match]
        ]
    
    @property
    def categories(self) -> List[str]:
        return sorted(self._categories.keys())
    
    def get_channels_by_category(self, category: str) -> List[Channel]:
        return self._categories.get(category, []) 