import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict

from core.models import EPGChannel, Program

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

        if tz:
            sign = 1 if tz.startswith("+") else -1
            if tz == "Z":
                offset = 0
            else:
                tz = tz.replace(":", "")
                offset = sign * (int(tz[1:3]) * 60 + int(tz[3:5]))
            dt = dt - timedelta(minutes=offset)
        return dt

    @staticmethod
    def parse(file_path: str) -> Dict[str, EPGChannel]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"EPG file not found: {file_path}")

        if os.path.getsize(file_path) == 0:
            raise ValueError("EPG file is empty")

        tree = ET.parse(file_path)
        root = tree.getroot()

        root_tag = root.tag.split("}")[-1]
        if root_tag != "tv":
            raise ValueError("Invalid XMLTV format: missing root 'tv'")

        epg_data: Dict[str, EPGChannel] = {}
        for program in root.findall(".//programme"):
            channel_id = program.get("channel")
            if not channel_id:
                continue

            try:
                start_time = EPGParser.parse_date(program.get("start", ""))
                end_time = EPGParser.parse_date(program.get("stop", ""))
            except ValueError as exc:
                logger.warning("Skipping program due to invalid date (%s): %s", channel_id, exc)
                continue

            title_node = program.find("title")
            title = (title_node.text or "No Title") if title_node is not None else "No Title"

            desc_node = program.find("desc")
            description = desc_node.text or "" if desc_node is not None else ""

            category_node = program.find("category")
            category = category_node.text or "" if category_node is not None else ""

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
        return epg_data
