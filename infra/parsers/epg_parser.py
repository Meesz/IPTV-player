import os
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict
from core.models import Program, EPGChannel

logger = logging.getLogger(__name__)

class EPGParser:
    """Utility class for parsing EPG data from XMLTV files."""

    @staticmethod
    def parse_date(date_str: str) -> datetime:
        """Parse various EPG date formats into a datetime object."""
        date_str = date_str.split("+")[0].split("-")[0]
        date_str = date_str.replace(" ", "").replace("T", "")

        try:
            return datetime.strptime(date_str, "%Y%m%d%H%M%S")
        except ValueError:
            try:
                return datetime.strptime(date_str, "%Y%m%d%H%M")
            except ValueError as exc:
                raise ValueError(f"Unsupported date format: {date_str}") from exc

    @staticmethod
    def parse(file_path: str) -> Dict[str, EPGChannel]:
        """Parse an XMLTV file and return a dictionary of EPGChannels."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"EPG file not found: {file_path}")

        if not os.path.getsize(file_path):
            raise ValueError("EPG file is empty")

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            if root.tag != "tv":
                raise ValueError("Invalid XMLTV format: missing root 'tv' element")

            epg_data: Dict[str, EPGChannel] = {}
            program_count = 0

            for program in root.findall(".//programme"):
                channel_id = program.get("channel")
                if not channel_id:
                    continue

                try:
                    start_time = EPGParser.parse_date(program.get("start", ""))
                    end_time = EPGParser.parse_date(program.get("stop", ""))
                except ValueError as e:
                    logger.warning(f"Skipping program due to invalid date: {e}")
                    continue

                title = program.find("title")
                title_text = title.text if title is not None else "No Title"

                desc = program.find("desc")
                desc_text = desc.text if desc is not None else ""

                category = program.find("category")
                category_text = category.text if category is not None else ""

                prog = Program(
                    title=title_text,
                    start_time=start_time,
                    end_time=end_time,
                    description=desc_text,
                    category=category_text,
                )

                if channel_id not in epg_data:
                    epg_data[channel_id] = EPGChannel(channel_id=channel_id)
                
                epg_data[channel_id].programs.append(prog)
                program_count += 1

            logger.info(f"EPG loaded: {len(epg_data)} channels, {program_count} programs")
            return epg_data

        except Exception as e:
            raise ValueError(f"Failed to parse EPG file: {str(e)}") from e
