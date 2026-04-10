import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import requests
from requests.exceptions import RequestException, Timeout

from core.errors import NetworkError, ParsingError
from core.models import EPGChannel, Program
from infra.db.epg_repository import EPGRepository
from infra.parsers.epg_parser import EPGParser

logger = logging.getLogger(__name__)


class EPGService:
    def __init__(self, repository: EPGRepository):
        self.repository = repository
        self._channels: Dict[str, EPGChannel] = {}

    def load_epg_from_path(self, path: str) -> None:
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"EPG file not found: {path}")
        try:
            self._channels = EPGParser.parse(str(path_obj))
            self.repository.save_all(
                {key: epg.channels for key, epg in self._channels.items()}
            )
        except Exception as exc:
            logger.error("Failed to load EPG file %s: %s", path, exc)
            raise ParsingError(f"Failed to parse EPG file: {path}") from exc

    def load_epg_from_url(self, url: str) -> None:
        response = None
        tmp_path: Path | None = None
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp_file:
                tmp_file.write(response.content)
                tmp_path = Path(tmp_file.name)
            self.load_epg_from_path(str(tmp_path))
        except Timeout as exc:
            raise NetworkError(f"Timed out loading EPG URL: {url}") from exc
        except RequestException as exc:
            raise NetworkError(f"Failed to download EPG URL: {url}") from exc
        except ParsingError:
            raise
        except Exception as exc:
            logger.error("Unexpected EPG URL load failure (%s): %s", url, exc)
            raise
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            if response is not None:
                response.close()

    def clear_epg(self) -> None:
        self._channels = {}
        self.repository.clear()

    def get_program_for_channel(self, channel_id: str, current_time=None) -> Optional[Program]:
        if channel_id in self._channels:
            return self._channels[channel_id].get_current_program(current_time)
        return self.repository.get_current_program(channel_id)

    def get_upcoming_programs(self, channel_id: str, limit: int = 5) -> List[Program]:
        if channel_id in self._channels:
            return self._channels[channel_id].get_upcoming_programs(limit=limit)
        return self.repository.get_upcoming_programs(channel_id, limit)

    @property
    def loaded_channels(self) -> List[str]:
        return sorted(self._channels.keys())
