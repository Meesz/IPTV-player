import gzip
import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Dict

from core.models import EPGChannel, ParseWarning, Program

logger = logging.getLogger(__name__)


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
        if len(base) == 12:
            dt = datetime.strptime(base, "%Y%m%d%H%M")
        else:
            dt = datetime.strptime(base, "%Y%m%d%H%M%S")

        if not tz or tz == "Z":
            return dt.replace(tzinfo=timezone.utc)

        normalized_tz = tz.replace(":", "")
        sign = 1 if normalized_tz.startswith("+") else -1
        offset = sign * (int(normalized_tz[1:3]) * 60 + int(normalized_tz[3:5]))
        aware = dt.replace(
            tzinfo=timezone(timedelta(minutes=offset))
        )
        return aware.astimezone(timezone.utc)

    @staticmethod
    def parse(file_path: str) -> Dict[str, EPGChannel]:
        parsed, _warnings = EPGParser.parse_with_warnings(file_path)
        return parsed

    @staticmethod
    def parse_with_warnings(file_path: str) -> tuple[Dict[str, EPGChannel], list[ParseWarning]]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"EPG file not found: {file_path}")

        if os.path.getsize(file_path) == 0:
            raise ValueError("EPG file is empty")

        with open(file_path, "rb") as stream:
            signature = stream.read(2)

        if signature == b"\x1f\x8b":
            with gzip.open(file_path, "rb") as stream:
                tree = ET.parse(stream)
        else:
            tree = ET.parse(file_path)
        root = tree.getroot()

        root_tag = EPGParser._local_name(root.tag)
        if root_tag != "tv":
            raise ValueError("Invalid XMLTV format: missing root 'tv'")

        epg_data: Dict[str, EPGChannel] = {}
        warnings: list[ParseWarning] = []
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

            epg_data.setdefault(channel_id, EPGChannel(channel_id=channel_id)).programs.append(program_model)

        if not epg_data:
            raise ValueError("No programs found in EPG file")

        logger.info("EPG loaded: %s channels, %s programs", len(epg_data), sum(len(v.programs) for v in epg_data.values()))
        return epg_data, warnings

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.split("}")[-1]

    @staticmethod
    def _child_text(node: ET.Element, child_name: str) -> str:
        for child in node:
            if EPGParser._local_name(child.tag) == child_name:
                return (child.text or "").strip()
        return ""
