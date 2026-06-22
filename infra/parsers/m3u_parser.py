import hashlib
import logging
import re
from pathlib import Path

from core.errors import ParsingError
from core.models import Channel, ParseWarning, Playlist

logger = logging.getLogger(__name__)


_EXTINF_RE = re.compile(
    # Duration is any number per the M3U spec (e.g. -1 for live, 0, or a real
    # length). Only the duration field is validated here; channels with a
    # non "-1" duration must not be dropped as malformed. The remainder (the
    # attributes plus the title) is split later, quote-aware, so a comma inside
    # a quoted attribute value does not get mistaken for the title separator.
    r"#EXTINF:\s*(?P<duration>-?\d+(?:\.\d+)?)(?P<rest>.*)$",
    re.IGNORECASE,
)
_ATTRIBUTE_RE = re.compile(r'(\w[\w-]*)=(?:"([^"]*)"|\'([^\']*)\')')


class M3UParser:
    """Parser for M3U/M3U8 playlists."""

    @staticmethod
    def parse(file_path: str | Path) -> Playlist:  # noqa: PLR0912, PLR0915  (parser dispatch; pre-existing size)
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

        parse_warnings: list[ParseWarning] = []
        playlist = Playlist(source_path=str(file_path), source_hash=file_path_hash)

        text = M3UParser._decode_playlist_content(payload, file_path)
        lines = text.splitlines()

        if not lines or not lines[0].lstrip().startswith("#EXTM3U"):
            raise ParsingError("Missing #EXTM3U header")

        pending_channel: dict[str, str] | None = None
        for line in lines[1:]:
            value = line.strip()
            if not value:
                continue

            if value.startswith("#EXTINF"):
                match = _EXTINF_RE.match(value)
                attrs_blob, raw_name = M3UParser._split_extinf_tail(match.group("rest")) if match else (None, None)
                if not match or raw_name is None:
                    parse_warnings.append(
                        ParseWarning(
                            code="invalid_extinf",
                            message="Skipped malformed EXTINF entry",
                            context=value[:80],
                        )
                    )
                    pending_channel = None
                    continue

                attrs = M3UParser._parse_attributes(attrs_blob)
                channel_name = raw_name.strip() or attrs.get("tvg-name") or "Unknown Channel"
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
                parse_warnings.append(
                    ParseWarning(
                        code="orphan_stream_url",
                        message="Skipped stream URL without a matching EXTINF record",
                        context=value[:80],
                    )
                )
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
                    channel.channel_number = M3UParser._parse_int_field(
                        pending_channel["channel_number"],
                        field_name="tvg-chno",
                        warnings=parse_warnings,
                        context=channel.name,
                    )
                if pending_channel.get("time_shift"):
                    channel.time_shift = M3UParser._parse_int_field(
                        pending_channel["time_shift"],
                        field_name="tvg-shift",
                        warnings=parse_warnings,
                        context=channel.name,
                    )
                playlist.add_channel(channel)
            except Exception as exc:
                parse_warnings.append(
                    ParseWarning(
                        code="invalid_channel_entry",
                        message=f"Skipped invalid playlist entry: {exc}",
                        context=value[:80],
                    )
                )
            finally:
                pending_channel = None

        if not playlist.channels:
            raise ParsingError("Playlist contains no channels")

        if parse_warnings:
            logger.warning(
                "M3U parse warnings in %s: %s",
                file_path,
                [warning.message for warning in parse_warnings[:5]],
            )
        playlist.parse_warnings = parse_warnings

        return playlist

    @staticmethod
    def _decode_playlist_content(content: bytes, source: Path) -> str:
        for encoding in (
            "utf-8-sig",
            "utf-8",
            "utf-16",
            "utf-16-le",
            "utf-16-be",
            "iso-8859-1",
            "cp1252",
        ):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ParsingError(f"Could not decode playlist with supported encodings: {source}")

    @staticmethod
    def _split_extinf_tail(rest: str) -> tuple[str | None, str | None]:
        """Split the EXTINF tail into ``(attributes, title)``.

        The title is separated from the attribute block by the first comma that
        is not inside a quoted attribute value, so commas inside values such as
        ``group-title="News, World"`` do not corrupt the channel name. Returns
        ``(rest, None)`` when no title separator exists (a malformed entry).
        """
        quote: str | None = None
        for index, char in enumerate(rest):
            if quote is not None:
                if char == quote:
                    quote = None
            elif char in ('"', "'"):
                quote = char
            elif char == ",":
                return rest[:index], rest[index + 1 :]
        return rest, None

    @staticmethod
    def _parse_attributes(raw: str) -> dict[str, str]:
        attributes: dict[str, str] = {}
        for match in _ATTRIBUTE_RE.finditer(raw):
            key = match.group(1).lower()
            value = match.group(2) if match.group(2) is not None else match.group(3) or ""
            attributes[key] = value
        return attributes

    @staticmethod
    def _parse_int_field(
        value: str,
        *,
        field_name: str,
        warnings: list[ParseWarning],
        context: str,
    ) -> int:
        try:
            return int(value)
        except ValueError:
            warnings.append(
                ParseWarning(
                    code="invalid_numeric_attribute",
                    message=f"Ignored invalid {field_name} value",
                    context=f"{context}: {value}",
                )
            )
            return 0
