import re
import logging
import hashlib
from pathlib import Path
from typing import TextIO, Dict, Optional, List
from core.models import Channel, Playlist

logger = logging.getLogger(__name__)

class M3UParser:
    """Utility class for parsing M3U/M3U8 playlist files."""

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
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"M3U file not found: {file_path}")

        playlist = Playlist()
        playlist.source_path = str(file_path)
        
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
            return playlist

        except UnicodeDecodeError:
            logger.warning(f"UTF-8 decode failed for {file_path}, trying ISO-8859-1")
            try:
                with open(file_path, "r", encoding="ISO-8859-1") as f:
                    M3UParser._validate_header(f)
                    channels = M3UParser._parse_channels(f)
                    for channel in channels:
                        playlist.add_channel(channel)
                return playlist
            except Exception as e:
                raise ValueError(f"Failed to parse playlist with multiple encodings") from e
        except Exception as e:
            raise ValueError(f"Error parsing M3U file: {str(e)}") from e

    @staticmethod
    def _validate_header(file: TextIO) -> None:
        first_line = file.readline().strip()
        if not first_line:
            raise ValueError("Empty M3U file")
        if not first_line.startswith("#EXTM3U"):
            raise ValueError("Invalid M3U file format - missing #EXTM3U header")

    @staticmethod
    def _parse_channels(file: TextIO) -> List[Channel]:
        channels: List[Channel] = []
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
            elif not line.startswith("#") and current_channel is not None:
                try:
                    channel_data = dict(current_channel)
                    
                    channel = Channel(
                        name=channel_data.get("name", "Unknown"),
                        url=line,
                        group=channel_data.get("group", "Uncategorized"),
                        logo=channel_data.get("logo", ""),
                        epg_id=channel_data.get("epg_id", ""),
                    )
                    
                    if "channel_number" in channel_data and channel_data["channel_number"]:
                        try:
                            channel.channel_number = int(channel_data["channel_number"])
                        except ValueError:
                            pass
                            
                    if "time_shift" in channel_data and channel_data["time_shift"]:
                        try:
                            channel.time_shift = int(channel_data["time_shift"])
                        except ValueError:
                            pass
                    
                    channels.append(channel)
                except Exception:
                    pass
                    
                current_channel = None

        return channels
