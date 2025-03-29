"""
This module contains the EPGController class, which is responsible for managing EPG data.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from models.epg import Program, EPG
from models.playlist import Channel
from utils.epg_parser import EPGParser
from controllers.base_controller import BaseController

logger = logging.getLogger(__name__)


class EPGController(BaseController):
    """Controller for managing EPG data.

    The EPGController is responsible for loading EPG data from a file,
    matching EPG data with channels, and retrieving program information for channels.
    """

    def __init__(self, config=None):
        """Initialize the EPGController with optional config.

        Args:
            config: Optional configuration parameters
        """
        super().__init__(config)
        self.epg: Optional[EPG] = None
        self.epg_path: Optional[str] = None
        self.channel_map: Dict[str, str] = {}  # Map from channel ID to EPG ID

    def load_epg(self, file_path: str) -> bool:
        """Load EPG data from a file.

        Args:
            file_path (str): Path to the EPG file

        Returns:
            bool: True if loading was successful, False otherwise
        """
        if not os.path.exists(file_path):
            logger.error(f"EPG file not found: {file_path}")
            return False

        try:
            self.epg = EPGParser.parse(file_path)
            self.epg_path = file_path
            logger.info(f"EPG loaded successfully from {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load EPG: {str(e)}")
            return False

    def reload_epg(self) -> bool:
        """Reload the EPG data from the previously loaded file.

        Returns:
            bool: True if reloading was successful, False otherwise
        """
        if not self.epg_path:
            logger.error("No EPG file has been loaded")
            return False
        return self.load_epg(self.epg_path)

    def map_channel_to_epg(self, channel: Channel, epg_id: str) -> None:
        """Map a channel to an EPG ID.

        Args:
            channel (Channel): The channel to map
            epg_id (str): The EPG ID to map to
        """
        if not self.epg:
            logger.warning("No EPG loaded, cannot map channel")
            return

        if epg_id not in self.epg.channels:
            logger.warning(f"EPG ID '{epg_id}' not found in EPG data")
            return

        self.channel_map[channel.id] = epg_id
        logger.debug(f"Mapped channel '{channel.name}' to EPG ID '{epg_id}'")

    def auto_map_channels(self, channels: List[Channel]) -> int:
        """Automatically map channels to EPG IDs based on channel name or ID.

        Args:
            channels (List[Channel]): List of channels to map

        Returns:
            int: Number of channels successfully mapped
        """
        if not self.epg:
            logger.warning("No EPG loaded, cannot auto-map channels")
            return 0

        mapped_count = 0
        for channel in channels:
            # Try to find a match in EPG data
            # First check if channel.tvg_id is in EPG
            if channel.tvg_id and channel.tvg_id in self.epg.channels:
                self.channel_map[channel.id] = channel.tvg_id
                mapped_count += 1
                continue

            # Then check if channel.name is in EPG
            if channel.name in self.epg.channels:
                self.channel_map[channel.id] = channel.name
                mapped_count += 1
                continue

            # Try other potential matches (lowercase, strip spaces, etc.)
            channel_name_clean = channel.name.lower().replace(" ", "")
            for epg_id in self.epg.channels:
                epg_id_clean = epg_id.lower().replace(" ", "")
                if channel_name_clean == epg_id_clean:
                    self.channel_map[channel.id] = epg_id
                    mapped_count += 1
                    break

        logger.info(f"Auto-mapped {mapped_count} of {len(channels)} channels to EPG data")
        return mapped_count

    def get_epg_id_for_channel(self, channel: Channel) -> Optional[str]:
        """Get the EPG ID mapped to a channel.

        Args:
            channel (Channel): The channel to get the EPG ID for

        Returns:
            Optional[str]: The mapped EPG ID, or None if no mapping exists
        """
        return self.channel_map.get(channel.id)

    def get_current_program(self, channel: Channel) -> Optional[Program]:
        """Get the current program for a channel.

        Args:
            channel (Channel): The channel to get the current program for

        Returns:
            Optional[Program]: The current program, or None if not found
        """
        if not self.epg:
            logger.warning("No EPG loaded, cannot get current program")
            return None

        epg_id = self.get_epg_id_for_channel(channel)
        if not epg_id:
            logger.debug(f"No EPG mapping for channel: {channel.name}")
            return None

        # Apply time shift if available
        time_shift = timedelta(hours=channel.time_shift or 0)
        current_time = datetime.now() - time_shift
        
        return self.epg.get_current_program(epg_id, current_time)

    def get_upcoming_programs(self, channel: Channel, hours: int = 24) -> List[Program]:
        """Get upcoming programs for a channel.

        Args:
            channel (Channel): The channel to get upcoming programs for
            hours (int): Number of hours to look ahead

        Returns:
            List[Program]: List of upcoming programs
        """
        if not self.epg:
            logger.warning("No EPG loaded, cannot get upcoming programs")
            return []

        epg_id = self.get_epg_id_for_channel(channel)
        if not epg_id:
            logger.debug(f"No EPG mapping for channel: {channel.name}")
            return []

        # Apply time shift if available
        time_shift = timedelta(hours=channel.time_shift or 0)
        current_time = datetime.now() - time_shift
        end_time = current_time + timedelta(hours=hours)
        
        return self.epg.get_upcoming_programs(epg_id, current_time, end_time)

    def get_program_at_time(self, channel: Channel, timestamp: datetime) -> Optional[Program]:
        """Get the program for a channel at a specific time.

        Args:
            channel (Channel): The channel to get the program for
            timestamp (datetime): The time to get the program for

        Returns:
            Optional[Program]: The program at the specified time, or None if not found
        """
        if not self.epg:
            logger.warning("No EPG loaded, cannot get program at time")
            return None

        epg_id = self.get_epg_id_for_channel(channel)
        if not epg_id:
            logger.debug(f"No EPG mapping for channel: {channel.name}")
            return None

        # Apply time shift if channel has one
        if channel.time_shift:
            time_shift = timedelta(hours=channel.time_shift)
            adjusted_time = timestamp - time_shift
        else:
            adjusted_time = timestamp

        programs = self.epg.get_channel_data(epg_id)
        if not programs:
            return None

        for program in programs:
            if program.start_time <= adjusted_time <= program.end_time:
                return program

        return None
