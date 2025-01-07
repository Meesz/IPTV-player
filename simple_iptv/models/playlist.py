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

class Playlist:
    def __init__(self):
        self.channels: List[Channel] = []
        self._categories: Dict[str, List[Channel]] = defaultdict(list)
    
    def add_channel(self, channel: Channel):
        self.channels.append(channel)
        category = channel.group or "Uncategorized"
        self._categories[category].append(channel)
    
    def clear(self):
        self.channels.clear()
        self._categories.clear()
    
    @property
    def categories(self) -> List[str]:
        return sorted(self._categories.keys())
    
    def get_channels_by_category(self, category: str) -> List[Channel]:
        return self._categories.get(category, []) 