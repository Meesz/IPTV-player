"""
This module contains the Channel class for representing IPTV channels.
"""

from dataclasses import dataclass


@dataclass
class Channel:
    """Represents a single channel in the playlist."""

    name: str
    url: str
    group: str = ""
    logo: str = ""
    epg_id: str = ""
    id: int = None

    def __hash__(self):
        """Generate a hash based on the channel's URL."""
        return hash(self.url)  # Use URL as unique identifier

    @staticmethod
    def from_db_row(row):
        """Create a Channel instance from a database row.

        Args:
            row (dict): A dictionary representing a database row with channel data.

        Returns:
            Channel: An instance of the Channel class.
        """
        return Channel(
            name=row["name"],
            url=row["url"],
            group=row["group_name"],
            logo=row["logo"],
            epg_id=row["epg_id"],
            id=row["id"],
        ) 