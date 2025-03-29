from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional
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

    def get_current_program(self, current_time: datetime = None) -> Optional[Program]:
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

    def get_upcoming_programs(self, current_time: datetime = None, limit: int = 5) -> List[Program]:
        """Get upcoming programs based on the provided time.

        Args:
            current_time (datetime, optional): The time to check against. Defaults to now.
            limit (int, optional): Maximum number of programs to return. Defaults to 5.

        Returns:
            List[Program]: List of upcoming programs.
        """
        if current_time is None:
            current_time = datetime.now()

        upcoming = [p for p in self.programs if p.start_time > current_time]
        upcoming.sort(key=lambda p: p.start_time)
        return upcoming[:limit]


class EPG:
    """Manages EPG data and provides methods to access program information."""

    def __init__(self):
        """Initialize the EPG with an empty data store."""
        self._channels: Dict[str, EPGData] = {}
        self._programs_count = 0

    def add_channel(self, channel_id: str, programs: List[Program] = None):
        """Add or update a channel with optional programs.

        Args:
            channel_id: The ID of the channel.
            programs: Optional list of programs for the channel.
        """
        if channel_id not in self._channels:
            self._channels[channel_id] = EPGData(channel_id=channel_id, programs=[])
        
        if programs:
            self._channels[channel_id].programs.extend(programs)
            self._programs_count += len(programs)

    def add_program(self, channel_id: str, program: Program):
        """Add a program to a channel.

        Args:
            channel_id: The ID of the channel.
            program: The program to add.
        """
        if channel_id not in self._channels:
            self.add_channel(channel_id)
            
        self._channels[channel_id].programs.append(program)
        self._programs_count += 1

    def get_channel_data(self, channel_id: str) -> Optional[EPGData]:
        """Get EPG data for a specific channel.

        Args:
            channel_id: The ID of the channel.

        Returns:
            The EPG data for the channel, or None if not found.
        """
        return self._channels.get(channel_id)

    def get_current_program(self, channel_id: str, reference_time: datetime = None) -> Optional[Program]:
        """Get the current program for a channel.

        Args:
            channel_id: The ID of the channel.
            reference_time: The time to check against. Defaults to now.

        Returns:
            The current program if found, otherwise None.
        """
        channel_data = self.get_channel_data(channel_id)
        if not channel_data:
            return None
            
        return channel_data.get_current_program(reference_time)

    def get_upcoming_programs(self, channel_id: str, reference_time: datetime = None, limit: int = 5) -> List[Program]:
        """Get upcoming programs for a channel.

        Args:
            channel_id: The ID of the channel.
            reference_time: The time to check against. Defaults to now.
            limit: Maximum number of programs to return. Defaults to 5.

        Returns:
            List of upcoming programs.
        """
        channel_data = self.get_channel_data(channel_id)
        if not channel_data:
            return []
            
        return channel_data.get_upcoming_programs(reference_time, limit)

    def clear(self):
        """Clear all EPG data."""
        self._channels.clear()
        self._programs_count = 0

    @property
    def channels(self) -> List[str]:
        """Get a list of all channel IDs in the EPG.

        Returns:
            List of channel IDs.
        """
        return list(self._channels.keys())
        
    @property
    def programs(self) -> List[Program]:
        """Get a list of all programs in the EPG.

        Returns:
            List of all programs.
        """
        all_programs = []
        for channel_data in self._channels.values():
            all_programs.extend(channel_data.programs)
        return all_programs
        
    def __len__(self):
        """Return the number of programs in the EPG."""
        return self._programs_count


class EPGGuide:
    """Deprecated class, maintained for compatibility."""

    def __init__(self):
        """Initialize with a warning."""
        import warnings
        warnings.warn("EPGGuide is deprecated, use EPG instead", DeprecationWarning, stacklevel=2)
        self._data: Dict[str, EPGData] = {}
        self._cache_timeout = timedelta(minutes=5)
        self._last_cache_clear = datetime.now()

    def add_channel_data(self, channel_id: str, epg_data: EPGData):
        """Add EPG data for a specific channel."""
        self._data[channel_id] = epg_data

    def get_channel_data(self, channel_id: str) -> Optional[EPGData]:
        """Retrieve EPG data for a specific channel."""
        return self._data.get(channel_id)

    def clear(self):
        """Clear all EPG data."""
        self._data.clear()

    @lru_cache(maxsize=100)
    def get_current_program(self, channel_id: str, timestamp: int) -> Optional[Program]:
        """Get current program with caching."""
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

    def get_channel_ids(self) -> List[str]:
        """Get a list of all channel IDs in the guide."""
        return list(self._data.keys())
