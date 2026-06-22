import contextlib
import logging
import tempfile
from collections.abc import Callable
from concurrent.futures import CancelledError
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from requests.exceptions import RequestException, Timeout

from core.errors import NetworkError, ParsingError, RepositoryError
from core.models import EPGChannel, ParseWarning, Program
from infra.db.epg_repository import EPGRepository
from infra.parsers.epg_parser import EPGParser

logger = logging.getLogger(__name__)


class EPGService:
    def __init__(self, repository: EPGRepository):
        self.repository = repository
        self._channels: dict[str, EPGChannel] = {}
        self._last_warnings: list[ParseWarning] = []

    def load_epg_from_path(
        self,
        path: str,
        *,
        progress_callback: Callable[[str], None] | None = None,
        cancel_callback: Callable[[], bool] | None = None,
    ) -> None:
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"EPG file not found: {path}")
        self._last_warnings = []
        self._ensure_not_cancelled(cancel_callback)
        parsed_channels: dict[str, EPGChannel]
        warnings: list[ParseWarning]
        try:
            self._emit_progress(progress_callback, "Parsing EPG data")
            parsed_channels, warnings = EPGParser.parse_with_warnings(str(path_obj))
        except ParsingError:
            raise
        except ValueError as exc:
            logger.error("Failed to load EPG file %s: %s", path, exc)
            raise ParsingError(f"Failed to parse EPG file: {path}") from exc
        except Exception as exc:
            logger.error("Unexpected EPG parser failure for %s: %s", path, exc)
            raise

        try:
            self._ensure_not_cancelled(cancel_callback)
            self._emit_progress(progress_callback, "Saving EPG cache")
            self.repository.save_all({key: epg.programs for key, epg in parsed_channels.items()})
        except RepositoryError:
            logger.error("Failed to persist EPG data for %s", path)
            raise
        self._ensure_not_cancelled(cancel_callback)
        self._channels = parsed_channels
        self._last_warnings = warnings

    def load_epg_from_url(
        self,
        url: str,
        *,
        progress_callback: Callable[[str], None] | None = None,
        cancel_callback: Callable[[], bool] | None = None,
    ) -> None:
        response = None
        tmp_path: Path | None = None
        try:
            self._ensure_not_cancelled(cancel_callback)
            self._emit_progress(progress_callback, "Downloading EPG")
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            parsed_url = urlparse(url)
            suffix = ".xml.gz" if parsed_url.path.endswith(".gz") else ".xml"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                tmp_file.write(response.content)
                tmp_path = Path(tmp_file.name)
            self.load_epg_from_path(
                str(tmp_path),
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
            )
        except Timeout as exc:
            raise NetworkError(f"Timed out loading EPG URL: {self._redact_url(url)}") from exc
        except RequestException as exc:
            raise NetworkError(f"Failed to download EPG URL: {self._redact_url(url)}") from exc
        except ParsingError:
            raise
        except Exception as exc:
            logger.error("Unexpected EPG URL load failure (%s): %s", self._redact_url(url), exc)
            raise
        finally:
            if tmp_path is not None:
                with contextlib.suppress(OSError):
                    tmp_path.unlink()
            if response is not None:
                response.close()

    def clear_epg(self) -> None:
        self._channels = {}
        self._last_warnings = []
        self.repository.clear()

    def get_program_for_channel(self, channel_id: str, current_time=None) -> Program | None:
        current_time = self._normalize_time(current_time)
        if channel_id in self._channels:
            return self._channels[channel_id].get_current_program(current_time)
        return self.repository.get_current_program(channel_id, current_time=current_time)

    def get_upcoming_programs(
        self,
        channel_id: str,
        limit: int = 5,
        current_time=None,
    ) -> list[Program]:
        current_time = self._normalize_time(current_time)
        if channel_id in self._channels:
            return self._channels[channel_id].get_upcoming_programs(
                current_time=current_time,
                limit=limit,
            )
        return self.repository.get_upcoming_programs(
            channel_id,
            limit,
            current_time=current_time,
        )

    @property
    def loaded_channels(self) -> list[str]:
        return sorted(self._channels.keys())

    @property
    def last_warnings(self) -> list[ParseWarning]:
        return list(self._last_warnings)

    @staticmethod
    def _redact_url(url: str) -> str:
        """Mask credentials so EPG source URLs never leak to logs or the UI.

        XMLTV/Xtream EPG endpoints commonly carry credentials either in the query
        string (``?username=...&password=...``) or as basic-auth userinfo
        (``http://user:pass@host/...``). Keep the scheme/host/path for diagnostics
        but redact the password in both forms so it cannot reach the log file or an
        error notification.
        """
        try:
            parsed = urlparse(url)
        except ValueError:
            return url

        netloc = parsed.netloc
        if parsed.password is not None:
            host = parsed.hostname or ""
            if parsed.port is not None:
                host = f"{host}:{parsed.port}"
            userinfo = parsed.username or ""
            netloc = f"{userinfo}:***@{host}" if userinfo else f":***@{host}"

        query = parsed.query
        if query:
            query = urlencode(
                [
                    (key, "***" if key.lower() in {"password", "pass", "pwd"} else value)
                    for key, value in parse_qsl(query, keep_blank_values=True)
                ]
            )

        if netloc == parsed.netloc and query == parsed.query:
            return url
        return urlunparse(parsed._replace(netloc=netloc, query=query))

    @staticmethod
    def _emit_progress(
        callback: Callable[[str], None] | None,
        message: str,
    ) -> None:
        if callback is not None:
            callback(message)

    @staticmethod
    def _normalize_time(current_time: datetime | None) -> datetime:
        if current_time is None:
            return datetime.now(UTC)
        if current_time.tzinfo is None:
            return current_time.replace(tzinfo=UTC)
        return current_time.astimezone(UTC)

    @staticmethod
    def _ensure_not_cancelled(callback: Callable[[], bool] | None) -> None:
        if callback is not None and callback():
            raise CancelledError("EPG load cancelled")
