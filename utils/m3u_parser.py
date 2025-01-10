"""
This module provides utilities for parsing M3U files.

It defines the M3UParser class, which can parse M3U files and extract channel information
including name, URL, group, logo, and EPG ID into a structured Playlist object.
"""
from pathlib import Path
from typing import Optional, Tuple, TextIO
import re
from models.playlist import Channel, Playlist


class M3UParser:
    """Utility class for parsing M3U/M3U8 playlist files."""

    # Regular expression for parsing EXTINF lines
    EXTINF_REGEX = re.compile(
        r'#EXTINF:-1'
        r'(?:.*?tvg-id="(.*?)")?'
        r'(?:.*?tvg-name="(.*?)")?'
        r'(?:.*?group-title="(.*?)")?'
        r'(?:.*?tvg-logo="(.*?)")?'
        r',(.+)$'
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
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                M3UParser._validate_header(f)
                channels = M3UParser._parse_channels(f)
                for channel in channels:
                    playlist.add_channel(channel)

            return playlist

        except UnicodeDecodeError as e:
            raise ValueError(f"Invalid file encoding - must be UTF-8: {e}") from e
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
        current_channel = None

        for line in file:
            line = line.strip()
            if not line:
                continue

            if line.startswith("#EXTINF"):
                match = M3UParser.EXTINF_REGEX.match(line)
                if match:
                    epg_id = match.group(1) or ""
                    name = match.group(2) or match.group(5)  # Fallback to title if no tvg-name
                    group = match.group(3) or ""
                    logo = match.group(4) or ""
                    current_channel = {
                        'name': name,
                        'group': group, 
                        'logo': logo,
                        'epg_id': epg_id
                    }

            elif not line.startswith("#") and current_channel:
                channel = Channel(
                    name=current_channel.get('name', ''),
                    url=line,
                    group=current_channel.get('group', ''),
                    logo=current_channel.get('logo', ''),
                    epg_id=current_channel.get('epg_id', '')
                )
                channels.append(channel)
                current_channel = None

        return channels
