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
    id: int = None  # Add this for database ID

    @classmethod
    def from_db_row(cls, row):
        """Create Channel from database row"""
        data = dict(row)
        # Map database column names to Channel attributes
        mapping = {
            'group_name': 'group',  # Map group_name from DB to group attribute
            'id': 'id'  # Keep ID if present
        }
        
        # Rename keys according to mapping
        for db_name, attr_name in mapping.items():
            if db_name in data:
                data[attr_name] = data.pop(db_name)
        
        # Remove any extra fields not in Channel class
        valid_fields = cls.__annotations__.keys()
        data = {k: v for k, v in data.items() if k in valid_fields}
        
        return cls(**data)

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