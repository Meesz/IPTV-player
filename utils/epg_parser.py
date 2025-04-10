"""
This module contains the EPGParser class, which is responsible for parsing EPG data from XMLTV files.
"""

import os
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from models.epg import Program, EPGData, EPGGuide, EPG

# Configure logger
logger = logging.getLogger(__name__)


class EPGParser:
    """Utility class for parsing EPG data from XMLTV files."""

    @staticmethod
    def parse_date(date_str: str) -> datetime:
        """Parse various EPG date formats into a datetime object.

        Args:
            date_str (str): The date string to parse.

        Returns:
            datetime: The parsed datetime object.

        Raises:
            ValueError: If the date string is in an unsupported format.
        """
        # Add timezone handling
        date_str = date_str.split("+")[0].split("-")[0]

        # Remove any spaces or 'T'
        date_str = date_str.replace(" ", "").replace("T", "")

        # Parse YYYYMMDDHHMMSS format
        try:
            return datetime.strptime(date_str, "%Y%m%d%H%M%S")
        except ValueError:
            # Try YYYYMMDDHHMM format
            try:
                return datetime.strptime(date_str, "%Y%m%d%H%M")
            except ValueError as exc:
                raise ValueError(f"Unsupported date format: {date_str}") from exc

    @staticmethod
    def parse(file_path: str) -> EPG:
        """Parse an XMLTV file and return an EPG object.

        Args:
            file_path (str): The path to the XMLTV file.

        Returns:
            EPG: An object containing the parsed EPG data.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file is empty or in an invalid format.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"EPG file not found: {file_path}")

        if not os.path.getsize(file_path):
            raise ValueError("EPG file is empty")

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            if root.tag != "tv":
                raise ValueError("Invalid XMLTV format: missing root 'tv' element")

            epg = EPG()
            channel_count = 0
            program_count = 0

            for program in root.findall(".//programme"):
                channel_id = program.get("channel")
                if not channel_id:
                    continue

                # Parse program data with new date parser
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

                # Add to EPG
                epg.add_program(channel_id, prog)
                program_count += 1
                
                # Create a channel if needed
                if channel_id not in epg.channels:
                    channel_count += 1

            logger.info(f"EPG loaded: {channel_count} channels, {program_count} programs")

            # Debug: Print some channel IDs
            channel_ids = epg.channels[:5] if len(epg.channels) > 5 else epg.channels
            logger.debug(f"Sample channel IDs: {channel_ids}")

            return epg

        except Exception as e:
            raise ValueError(f"Failed to parse EPG file: {str(e)}") from e

    @staticmethod
    def parse_xmltv(file_path: str) -> EPGGuide:
        """Parse an XMLTV file and return an EPGGuide object (legacy method).

        Args:
            file_path (str): The path to the XMLTV file.

        Returns:
            EPGGuide: An object containing the parsed EPG data.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file is empty or in an invalid format.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"EPG file not found: {file_path}")

        if not os.path.getsize(file_path):
            raise ValueError("EPG file is empty")

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            if root.tag != "tv":
                raise ValueError("Invalid XMLTV format: missing root 'tv' element")

            guide = EPGGuide()
            channel_count = 0
            program_count = 0

            for program in root.findall(".//programme"):
                channel_id = program.get("channel")
                if not channel_id:
                    continue

                # Parse program data with new date parser
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

                # Add to guide
                channel_data = guide.get_channel_data(channel_id)
                if channel_data is None:
                    channel_data = EPGData(channel_id=channel_id, programs=[])
                    guide.add_channel_data(channel_id, channel_data)
                    channel_count += 1

                channel_data.programs.append(prog)
                program_count += 1

            logger.info(f"EPG loaded: {channel_count} channels, {program_count} programs")
            return guide

        except Exception as e:
            raise ValueError(f"Failed to parse EPG file: {str(e)}") from e
