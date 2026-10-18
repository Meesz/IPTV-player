import gzip
import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta, timezone

from core import limits
from core.models import EPGChannel, ParseWarning, Program

logger = logging.getLogger(__name__)


class _LimitedReader:
    """File-like wrapper that refuses to yield more than ``limit`` decompressed bytes."""

    def __init__(self, stream, limit: int):
        self._stream = stream
        self._limit = limit
        self._count = 0

    def read(self, size: int = -1) -> bytes:
        # Never request more than one byte past the limit so a bomb cannot inflate in memory.
        remaining = self._limit - self._count + 1
        size = remaining if size is None or size < 0 else min(size, remaining)
        data = self._stream.read(size)
        self._count += len(data)
        if self._count > self._limit:
            raise ValueError(f"Decompressed EPG data exceeds the {self._limit} byte limit")
        return data


class EPGParser:
    """Parser for XMLTV EPG payloads."""

    @staticmethod
    def parse_date(date_str: str) -> datetime:
        if not date_str:
            raise ValueError("Empty date")
        normalized = date_str.strip()
        match = re.match(r"^(\d{14})(?:\s*([+-]\d{4}|[+-]\d{2}:\d{2}|Z))?", normalized)
        if not match:
            match = re.match(r"^(\d{12})(?:\s*([+-]\d{4}|[+-]\d{2}:\d{2}|Z))?", normalized)
            if not match:
                raise ValueError(f"Unsupported date format: {date_str}")

        base = match.group(1)
        tz = match.group(2)
        dt = datetime.strptime(base, "%Y%m%d%H%M") if len(base) == 12 else datetime.strptime(base, "%Y%m%d%H%M%S")

        if not tz or tz == "Z":
            return dt.replace(tzinfo=UTC)

        normalized_tz = tz.replace(":", "")
        sign = 1 if normalized_tz.startswith("+") else -1
        offset = sign * (int(normalized_tz[1:3]) * 60 + int(normalized_tz[3:5]))
        aware = dt.replace(tzinfo=timezone(timedelta(minutes=offset)))
        return aware.astimezone(UTC)

    @staticmethod
    def parse(file_path: str) -> dict[str, EPGChannel]:
        parsed, _warnings = EPGParser.parse_with_warnings(file_path)
        return parsed

    @staticmethod
    def parse_with_warnings(file_path: str) -> tuple[dict[str, EPGChannel], list[ParseWarning]]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"EPG file not found: {file_path}")

        if os.path.getsize(file_path) == 0:
            raise ValueError("EPG file is empty")

        root = EPGParser._read_root(file_path)

        root_tag = EPGParser._local_name(root.tag)
        if root_tag != "tv":
            raise ValueError("Invalid XMLTV format: missing root 'tv'")

        epg_data: dict[str, EPGChannel] = {}
        warnings: list[ParseWarning] = []
        seen: dict[tuple[str, int], int] = {}
        duplicates = 0
        for program in root.iter():
            if EPGParser._local_name(program.tag) != "programme":
                continue
            channel_id = program.get("channel")
            if not channel_id:
                continue

            try:
                start_time = EPGParser.parse_date(program.get("start", ""))
                end_time = EPGParser.parse_date(program.get("stop", ""))
            except ValueError as exc:
                logger.warning("Skipping program due to invalid date (%s): %s", channel_id, exc)
                warnings.append(
                    ParseWarning(
                        code="invalid_program_date",
                        message=f"Skipped programme with invalid date for channel '{channel_id}'",
                        context=str(exc),
                    )
                )
                continue

            title = EPGParser._child_text(program, "title") or "No Title"
            description = EPGParser._child_text(program, "desc")
            category = EPGParser._child_text(program, "category")

            program_model = Program(
                title=title.strip(),
                start_time=start_time,
                end_time=end_time,
                description=(description or "").strip(),
                category=category.strip(),
            )

            channel = epg_data.setdefault(channel_id, EPGChannel(channel_id=channel_id))
            # Same key granularity as the DB (channel, whole-second UTC start):
            # a later duplicate replaces the earlier one in place.
            key = (channel_id, int(start_time.timestamp()))
            existing_index = seen.get(key)
            if existing_index is None:
                seen[key] = len(channel.programs)
                channel.programs.append(program_model)
            else:
                channel.programs[existing_index] = program_model
                duplicates += 1

        if not epg_data:
            raise ValueError("No programs found in EPG file")

        if duplicates:
            warnings.append(
                ParseWarning(
                    code="duplicate_programme",
                    message=f"Replaced {duplicates} duplicate programme(s) sharing channel and start time",
                    context=f"{duplicates} duplicate(s)",
                )
            )

        logger.info(
            "EPG loaded: %s channels, %s programs", len(epg_data), sum(len(v.programs) for v in epg_data.values())
        )
        return epg_data, warnings

    @staticmethod
    def _read_root(file_path: str) -> ET.Element:
        with open(file_path, "rb") as stream:
            signature = stream.read(2)

        try:
            if signature == b"\x1f\x8b":
                with gzip.open(file_path, "rb") as stream:
                    tree = ET.parse(_LimitedReader(stream, limits.MAX_EPG_DECOMPRESSED_BYTES))
            else:
                tree = ET.parse(file_path)
        except ET.ParseError as exc:
            line, column = exc.position
            raise ValueError(f"Malformed XML in EPG file (line {line}, column {column}): {exc}") from exc
        return tree.getroot()

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", maxsplit=1)[-1]

    @staticmethod
    def _child_text(node: ET.Element, child_name: str) -> str:
        for child in node:
            if EPGParser._local_name(child.tag) == child_name:
                return (child.text or "").strip()
        return ""
