"""
This module provides utilities for parsing M3U files.

It defines the M3UParser class, which can parse M3U files and
return a Playlist object containing the parsed channels.
"""

import re
from models.playlist import Channel, Playlist


class M3UParser:
    """Utility class for parsing M3U files."""

    @staticmethod
    def parse(file_path: str) -> Playlist:
        """Parse an M3U file and return a Playlist object.

        Args:
            file_path (str): The path to the M3U file.

        Returns:
            Playlist: An object containing the parsed channels.
        """
        playlist = Playlist()

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if not lines:
                raise ValueError("Empty M3U file")

            if not lines[0].strip().startswith("#EXTM3U"):
                raise ValueError("Invalid M3U file format")

            current_channel = None
            channels_count = 0

            for line_num, line in enumerate(lines[1:], 1):
                line = line.strip()
                if not line:
                    continue

                if line.startswith("#EXTINF"):
                    info_regex = r'#EXTINF:-1(?:.*tvg-id="(.*?)")?(?:.*tvg-name="(.*?)")?(?:.*group-title="(.*?)")?(?:.*tvg-logo="(.*?)")?,(.+)$'
                    match = re.match(info_regex, line)

                    if match:
                        epg_id = match.group(1) or ""
                        name = match.group(2) or match.group(5)
                        group = match.group(3) or ""
                        logo = match.group(4) or ""
                        current_channel = (name, group, logo, epg_id)

                elif not line.startswith("#") and current_channel:
                    name, group, logo, epg_id = current_channel
                    channel = Channel(
                        name=name, url=line, group=group, logo=logo, epg_id=epg_id
                    )
                    playlist.add_channel(channel)
                    channels_count += 1
                    current_channel = None

            return playlist

        except Exception as e:
            raise ValueError(f"Error parsing M3U file: {str(e)}") from e
