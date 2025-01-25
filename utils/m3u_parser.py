"""
This module provides utilities for parsing M3U files.

It defines the M3UParser class, which can parse M3U files and extract channel information
including name, URL, group, logo, and EPG ID into a structured Playlist object.
"""

from pathlib import Path
from typing import TextIO
import re
from models.channel import Channel
import unicodedata


class M3UParser:
    """Utility class for parsing M3U/M3U8 playlist files."""

    # Updated regex to be more flexible with content types
    EXTINF_REGEX = re.compile(
        r"#EXTINF:-1"
        r'(?:[^"]*?tvg-id="([^"]*)")?'
        r'(?:[^"]*?tvg-name="([^"]*)")?'
        r'(?:[^"]*?group-title="([^"]*)")?'
        r'(?:[^"]*?tvg-logo="([^"]*)")?'
        r',\s*(.*?)$'
    )

    @staticmethod
    def parse(file_path: str | Path) -> list[Channel]:
        """Parse an M3U/M3U8 file and return a list of channels."""
        print("\n=== Starting M3U Parser ===")
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"M3U file not found: {file_path}")

        print(f"Parsing file: {file_path}")
        print(f"File size: {file_path.stat().st_size} bytes")

        # Try different encodings in order of likelihood
        encodings = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
        errors = []
        
        # First try to detect encoding
        try:
            # Remove the encoding parameter from open() since we're reading in binary mode
            with open(file_path, 'rb') as f:
                raw_content = f.read()
                print(f"\nRaw content size: {len(raw_content)} bytes")
                print(f"First 100 bytes as hex: {raw_content[:100].hex()}")
                
                # Try to detect BOM
                if raw_content.startswith(b'\xef\xbb\xbf'):
                    print("UTF-8 BOM detected")
                    encodings.insert(0, 'utf-8-sig')
                
                # Try each encoding on the raw content first
                for encoding in encodings:
                    try:
                        decoded_content = raw_content.decode(encoding)
                        if decoded_content.strip().startswith('#EXTM3U'):
                            print(f"\nFound working encoding: {encoding}")
                            # Process the decoded content directly
                            lines = decoded_content.splitlines()
                            if not lines:
                                continue
                                
                            # Validate header
                            if not lines[0].strip().startswith('#EXTM3U'):
                                continue
                                
                            # Create a TextIO-like object from the lines
                            from io import StringIO
                            file_like = StringIO('\n'.join(lines))
                            
                            # Parse channels
                            channels = M3UParser._parse_channels(file_like)
                            return channels
                    except UnicodeError as e:
                        error_msg = f"Failed with {encoding}: {str(e)}"
                        print(error_msg)
                        errors.append(error_msg)
                        continue
                    except Exception as e:
                        error_msg = f"Error with {encoding}: {str(e)}"
                        print(error_msg)
                        errors.append(error_msg)
                        continue

        except Exception as e:
            print(f"Error reading file: {e}")
            raise ValueError(f"Failed to read playlist file: {str(e)}") from e

        raise ValueError(f"Failed to decode playlist file with any encoding. Errors: {'; '.join(errors)}")

    @staticmethod
    def _validate_header(file: TextIO) -> None:
        """Validate the M3U file header.

        Args:
            file: Open file handle to read from.

        Raises:
            ValueError: If file is empty or has invalid header.
        """
        first_line = file.readline().strip()
        print(f"First line read for validation: '{first_line}'")
        if not first_line:
            raise ValueError("Empty M3U file")
        if not first_line.startswith("#EXTM3U"):
            raise ValueError("Invalid M3U file format - missing #EXTM3U header")
        print("Header validation passed.")

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """Sanitize text by replacing problematic characters with safe alternatives."""
        if not text:
            return ""
        
        try:
            # First try to normalize unicode characters
            text = unicodedata.normalize('NFKD', text)
            
            # Replace any remaining problematic characters
            replacements = {
                '\u025b': 'e',    # LATIN SMALL LETTER OPEN E
                '\u0153': 'oe',   # LATIN SMALL LIGATURE OE
                '\u0152': 'OE',   # LATIN CAPITAL LIGATURE OE
                '\u2013': '-',    # EN DASH
                '\u2014': '-',    # EM DASH
                '\u2018': "'",    # LEFT SINGLE QUOTATION MARK
                '\u2019': "'",    # RIGHT SINGLE QUOTATION MARK
                '\u201c': '"',    # LEFT DOUBLE QUOTATION MARK
                '\u201d': '"',    # RIGHT DOUBLE QUOTATION MARK
                '\u2026': '...',  # HORIZONTAL ELLIPSIS
            }
            
            for char, replacement in replacements.items():
                text = text.replace(char, replacement)
            
            # Convert to ASCII, ignoring non-ASCII characters
            text = text.encode('ascii', errors='ignore').decode('ascii')
            
            return text.strip()
        except Exception as e:
            print(f"Warning: Error in text sanitization: {e}")
            return text.encode('ascii', errors='ignore').decode('ascii').strip()

    @staticmethod
    def _parse_channels(file: TextIO) -> list[Channel]:
        """Parse channel information from the M3U file content."""
        channels: list[Channel] = []
        current_channel = None
        skipped_count = 0

        for line in file:
            try:
                line = line.strip()
                if not line:
                    continue

                if line.startswith("#EXTINF"):
                    match = M3UParser.EXTINF_REGEX.match(line)
                    if match:
                        # Get raw values and sanitize them
                        epg_id = M3UParser._sanitize_text(match.group(1) or "")
                        name = M3UParser._sanitize_text(match.group(2) or match.group(5) or "")
                        group = M3UParser._sanitize_text(match.group(3) or "")
                        logo = match.group(4) or ""  # Don't sanitize URLs
                        
                        # Skip VOD/Series entries
                        if any(x in group.lower() for x in ['movie', 'film', 'series', 'vod']):
                            skipped_count += 1
                            current_channel = None
                            continue

                        current_channel = {
                            "name": name or "Unnamed Channel",
                            "group": group or "Uncategorized",
                            "logo": logo,
                            "epg_id": epg_id,
                        }

                elif not line.startswith("#") and current_channel:
                    # Only create channel if we have both info and URL
                    if line.startswith(("http://", "https://", "rtmp://", "rtsp://")):
                        try:
                            channel = Channel(
                                name=current_channel["name"],
                                url=line,
                                group=current_channel["group"],
                                logo=current_channel["logo"],
                                epg_id=current_channel["epg_id"],
                            )
                            channels.append(channel)
                        except Exception as e:
                            print(f"Warning: Failed to create channel: {e}")
                    current_channel = None

            except Exception as e:
                print(f"Warning: Error processing line: {e}")
                continue

        if skipped_count > 0:
            print(f"Skipped {skipped_count} VOD/Series entries")
        print(f"Successfully parsed {len(channels)} live TV channels")
        return channels
