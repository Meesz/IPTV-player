import hashlib
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from core.errors import ParsingError
from core.models import Channel, Playlist

logger = logging.getLogger(__name__)


_EXTINF_RE = re.compile(
    r"#EXTINF:-1(?P<attrs>[^,]*),(?P<name>.*)$",
    re.IGNORECASE,
)
_ATTRIBUTE_RE = re.compile(r'(\w[\w-]*)="([^"]*)"')


class M3UParser:
    """Parser for M3U/M3U8 playlists."""

    @staticmethod
    def parse(file_path: str | Path) -> Playlist:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"M3U file not found: {file_path}")

        if not file_path.is_file():
            raise ParsingError(f"Playlist path is not a file: {file_path}")

        try:
            payload = file_path.read_bytes()
            file_path_hash = hashlib.md5(payload).hexdigest()
        except OSError as exc:
            raise ParsingError(f"Could not read playlist file: {file_path}") from exc

        parse_errors: List[str] = []
        playlist = Playlist(source_path=str(file_path), source_hash=file_path_hash)

        text = M3UParser._decode_playlist_content(payload, file_path)
        lines = text.splitlines()

        if not lines or not lines[0].lstrip().startswith("#EXTM3U"):
            raise ParsingError("Missing #EXTM3U header")

        pending_channel: Optional[Dict[str, str]] = None
        for line in lines[1:]:
            value = line.strip()
            if not value:
                continue

            if value.startswith("#EXTINF"):
                match = _EXTINF_RE.match(value)
                if not match:
                    parse_errors.append(f"Invalid EXTINF line: {value[:80]}")
                    pending_channel = None
                    continue

                attrs = M3UParser._parse_attributes(match.group("attrs"))
                channel_name = (match.group("name") or "").strip() or attrs.get("tvg-name") or "Unknown Channel"
                pending_channel = {
                    "name": channel_name,
                    "group": attrs.get("group-title", "Uncategorized"),
                    "logo": attrs.get("tvg-logo", ""),
                    "epg_id": attrs.get("tvg-id", ""),
                    "channel_number": attrs.get("tvg-chno", ""),
                    "time_shift": attrs.get("tvg-shift", ""),
                }
                continue

            if value.startswith("#"):
                continue

            if pending_channel is None:
                continue

            try:
                channel = Channel(
                    name=pending_channel.get("name", "Unknown Channel"),
                    url=value,
                    group=pending_channel.get("group", "Uncategorized"),
                    logo=pending_channel.get("logo", ""),
                    epg_id=pending_channel.get("epg_id", ""),
                )
                if pending_channel.get("channel_number"):
                    channel.channel_number = int(pending_channel["channel_number"])
                if pending_channel.get("time_shift"):
                    channel.time_shift = int(pending_channel["time_shift"])
                playlist.add_channel(channel)
            except Exception as exc:
                parse_errors.append(f"Skipping invalid entry {value[:80]}: {exc}")
            finally:
                pending_channel = None

        if not playlist.channels:
            raise ParsingError(
                "Playlist contains no channels"
            )

        if parse_errors:
            logger.warning("M3U parse warnings in %s: %s", file_path, parse_errors[:5])

        return playlist

    @staticmethod
    def _decode_playlist_content(content: bytes, source: Path) -> str:
        for encoding in ("utf-8", "iso-8859-1", "cp1252"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ParsingError(f"Could not decode playlist with supported encodings: {source}")

    @staticmethod
    def _parse_attributes(raw: str) -> Dict[str, str]:
        return {key.lower(): value for key, value in _ATTRIBUTE_RE.findall(raw)}
