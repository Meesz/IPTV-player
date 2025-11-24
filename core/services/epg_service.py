import logging
from typing import Optional, List, Dict
from datetime import datetime
from core.models import Program, EPGChannel
from infra.parsers.epg_parser import EPGParser
from infra.db.epg_repository import EPGRepository

logger = logging.getLogger(__name__)

class EPGService:
    def __init__(self, repository: EPGRepository):
        self.repository = repository
        self._channels: Dict[str, EPGChannel] = {}

    def load_epg(self, path: str) -> None:
        """Load EPG data from a file."""
        logger.info(f"Loading EPG from: {path}")
        self._channels = EPGParser.parse(path)
        # Optionally persist to DB? The requirements say "Provide EPG current/upcoming programs"
        # and "EPGRepository" exists.
        # If we load from XML, we might want to cache it in DB or just keep in memory.
        # The existing implementation seemed to parse XML on load.
        # Let's keep it in memory for now, but also allow saving to DB if needed.
        
    def get_program_for_channel(self, channel_id: str, current_time: Optional[datetime] = None) -> Optional[Program]:
        if channel_id in self._channels:
            return self._channels[channel_id].get_current_program(current_time)
        # Fallback to DB if not in memory?
        return self.repository.get_current_program(channel_id)

    def get_upcoming_programs(self, channel_id: str, limit: int = 5) -> List[Program]:
        if channel_id in self._channels:
            return self._channels[channel_id].get_upcoming_programs(limit=limit)
        return self.repository.get_upcoming_programs(channel_id, limit)
