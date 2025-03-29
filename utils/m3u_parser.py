"""
This module provides utilities for parsing M3U files.

It defines the M3UParser class, which can parse M3U files and extract channel information
including name, URL, group, logo, and EPG ID into a structured Playlist object.
"""

from pathlib import Path
from typing import TextIO, Dict, Optional, Any
import re
import logging
import hashlib
from models.playlist import Channel, Playlist

# Configure logger
logger = logging.getLogger(__name__)

class M3UParser:
    """Utility class for parsing M3U/M3U8 playlist files."""

    # Regular expression for parsing EXTINF lines with extended attributes
    EXTINF_REGEX = re.compile(
        r"#EXTINF:-1"
        r'(?:.*?tvg-id="(.*?)")?'
        r'(?:.*?tvg-name="(.*?)")?'
        r'(?:.*?group-title="(.*?)")?'
        r'(?:.*?tvg-logo="(.*?)")?'
        r'(?:.*?tvg-chno="(.*?)")?'
        r'(?:.*?tvg-shift="(.*?)")?'
        r",(.+)$"
    )

    @staticmethod
    def parse(file_path: str | Path) -> Playlist:
        """Parse an M3U/M3U8 file and return a Playlist object.

        Args:
            file_path: Path to the M3U file as string or Path object.

        Returns:
            Playlist: Object containing the parsed channels.

        Raises:
            ValueError: If the file is empty, invalid format, or parsing fails.
            FileNotFoundError: If the specified file does not exist.
            UnicodeDecodeError: If the file encoding is not UTF-8.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"M3U file not found: {file_path}")

        playlist = Playlist()
        playlist.source_path = str(file_path)
        
        # Calculate source hash for caching
        try:
            with open(file_path, "rb") as f:
                content = f.read()
                playlist.source_hash = hashlib.md5(content).hexdigest()
        except Exception as e:
            logger.warning(f"Could not calculate source hash: {e}")
            playlist.source_hash = ""

        try:
            # Try UTF-8 first
            with open(file_path, "r", encoding="utf-8") as f:
                M3UParser._validate_header(f)
                channels = M3UParser._parse_channels(f)
                for channel in channels:
                    playlist.add_channel(channel)

            logger.info(f"Successfully parsed {len(playlist.channels)} channels from {file_path}")
            return playlist

        except UnicodeDecodeError:
            logger.warning(f"UTF-8 decode failed for {file_path}, trying ISO-8859-1")
            # Fallback to ISO-8859-1 if UTF-8 fails
            try:
                with open(file_path, "r", encoding="ISO-8859-1") as f:
                    M3UParser._validate_header(f)
                    channels = M3UParser._parse_channels(f)
                    for channel in channels:
                        playlist.add_channel(channel)
                
                logger.info(f"Successfully parsed {len(playlist.channels)} channels from {file_path} using ISO-8859-1")
                return playlist
            except Exception as e:
                logger.error(f"Failed to parse with ISO-8859-1: {e}")
                raise ValueError(f"Failed to parse playlist with multiple encodings") from e
        except Exception as e:
            raise ValueError(f"Error parsing M3U file: {str(e)}") from e

    @staticmethod
    def _validate_header(file: TextIO) -> None:
        """Validate the M3U file header.

        Args:
            file: Open file handle to read from.

        Raises:
            ValueError: If file is empty or has invalid header.
        """
        first_line = file.readline().strip()
        if not first_line:
            raise ValueError("Empty M3U file")
        if not first_line.startswith("#EXTM3U"):
            raise ValueError("Invalid M3U file format - missing #EXTM3U header")

    @staticmethod
    def _parse_channels(file: TextIO) -> list[Channel]:
        """Parse channel information from the M3U file content.

        Args:
            file: Open file handle positioned after header.

        Returns:
            List of parsed Channel objects.
        """
        channels: list[Channel] = []
        current_channel: Optional[Dict[str, str]] = None

        for line in file:
            line = line.strip()
            if not line:
                continue

            if line.startswith("#EXTINF"):
                match = M3UParser.EXTINF_REGEX.match(line)
                if match:
                    epg_id = match.group(1) or ""
                    name = match.group(2) or match.group(7) or "Unknown Channel"
                    group = match.group(3) or "Uncategorized"
                    logo = match.group(4) or ""
                    channel_number = match.group(5) or ""
                    time_shift = match.group(6) or "0"
                    
                    current_channel = {
                        "name": name,
                        "group": group,
                        "logo": logo,
                        "epg_id": epg_id,
                        "channel_number": channel_number,
                        "time_shift": time_shift
                    }
            # Handle url lines (non-comment lines that follow an EXTINF line)
            elif not line.startswith("#") and current_channel is not None:
                try:
                    channel_data = dict(current_channel)  # Make a copy to avoid reference issues
                    
                    # Create channel with all available metadata
                    channel = Channel(
                        name=channel_data.get("name", "Unknown"),
                        url=line,
                        group=channel_data.get("group", "Uncategorized"),
                        logo=channel_data.get("logo", ""),
                        epg_id=channel_data.get("epg_id", ""),
                    )
                    
                    # Add additional properties
                    if "channel_number" in channel_data and channel_data["channel_number"]:
                        try:
                            channel.channel_number = int(channel_data["channel_number"])
                        except ValueError:
                            logger.warning(f"Invalid channel number: {channel_data['channel_number']}")
                            
                    if "time_shift" in channel_data and channel_data["time_shift"]:
                        try:
                            channel.time_shift = int(channel_data["time_shift"])
                        except ValueError:
                            logger.warning(f"Invalid time shift: {channel_data['time_shift']}")
                    
                    channels.append(channel)
                except Exception as e:
                    logger.warning(f"Error creating channel from line '{line}': {str(e)}")
                    
                current_channel = None

        return channels
