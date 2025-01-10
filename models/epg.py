from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict
from functools import lru_cache


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
        """Calculate the duration of the program in minutes."""
        return int((self.end_time - self.start_time).total_seconds() / 60)


@dataclass
class EPGData:
    """Holds EPG data for a specific channel."""
    channel_id: str
    programs: List[Program]

    def get_current_program(self, current_time: datetime = None) -> Program:
        """Get the current program based on the provided time.

        Args:
            current_time (datetime, optional): The time to check against. Defaults to now.

        Returns:
            Program: The current program if found, otherwise None.
        """
        if current_time is None:
            current_time = datetime.now()

        for program in self.programs:
            if program.start_time <= current_time < program.end_time:
                return program
        return None


class EPGGuide:
    """Manages EPG data and provides methods to access current programs."""
    def __init__(self):
        """Initialize the EPGGuide with an empty data store and cache settings."""
        self._data: Dict[str, EPGData] = {}
        self._cache_timeout = timedelta(minutes=5)
        self._last_cache_clear = datetime.now()

    def add_channel_data(self, channel_id: str, epg_data: EPGData):
        """Add EPG data for a specific channel.

        Args:
            channel_id (str): The ID of the channel.
            epg_data (EPGData): The EPG data to add.
        """
        self._data[channel_id] = epg_data

    def get_channel_data(self, channel_id: str) -> EPGData:
        """Retrieve EPG data for a specific channel.

        Args:
            channel_id (str): The ID of the channel.

        Returns:
            EPGData: The EPG data for the channel, or None if not found.
        """
        return self._data.get(channel_id)

    def clear(self):
        """Clear all EPG data."""
        self._data.clear()

    @lru_cache(maxsize=100)
    def get_current_program(self, channel_id: str, timestamp: int) -> Program:
        """Get current program with caching.

        Args:
            channel_id (str): The ID of the channel.
            timestamp (int): The current timestamp.

        Returns:
            Program: The current program if found, otherwise None.
        """
        epg_data = self._data.get(channel_id)
        if not epg_data:
            return None

        current_time = datetime.fromtimestamp(timestamp)
        return epg_data.get_current_program(current_time)

    def clear_cache(self):
        """Clear the program cache periodically."""
        now = datetime.now()
        if now - self._last_cache_clear > self._cache_timeout:
            self.get_current_program.cache_clear()
            self._last_cache_clear = now

    def force_clear_cache(self):
        """Force clear the program cache immediately."""
        self.get_current_program.cache_clear()
        self._last_cache_clear = datetime.now()
