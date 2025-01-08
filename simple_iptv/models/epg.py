from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict
from functools import lru_cache

@dataclass
class Program:
    title: str
    start_time: datetime
    end_time: datetime
    description: str = ""
    category: str = ""
    
    @property
    def duration_minutes(self) -> int:
        return int((self.end_time - self.start_time).total_seconds() / 60)

@dataclass
class EPGData:
    channel_id: str
    programs: List[Program]
    
    def get_current_program(self, current_time: datetime = None) -> Program:
        if current_time is None:
            current_time = datetime.now()
            
        for program in self.programs:
            if program.start_time <= current_time < program.end_time:
                return program
        return None

class EPGGuide:
    def __init__(self):
        self._data: Dict[str, EPGData] = {}
        self._cache_timeout = timedelta(minutes=5)
        self._last_cache_clear = datetime.now()
    
    def add_channel_data(self, channel_id: str, epg_data: EPGData):
        self._data[channel_id] = epg_data
    
    def get_channel_data(self, channel_id: str) -> EPGData:
        return self._data.get(channel_id)
    
    def clear(self):
        self._data.clear() 
    
    @lru_cache(maxsize=100)
    def get_current_program(self, channel_id: str, timestamp: int) -> Program:
        """Get current program with caching"""
        epg_data = self._data.get(channel_id)
        if not epg_data:
            return None
            
        current_time = datetime.fromtimestamp(timestamp)
        return epg_data.get_current_program(current_time)
    
    def clear_cache(self):
        """Clear the program cache periodically"""
        now = datetime.now()
        if now - self._last_cache_clear > self._cache_timeout:
            self.get_current_program.cache_clear()
            self._last_cache_clear = now 