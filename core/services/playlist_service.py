import logging
import os
import tempfile
from pathlib import Path
from typing import List, Optional

import requests
from requests.exceptions import RequestException, Timeout

from core.errors import NetworkError, ParsingError, ValidationError
from core.models import Playlist, PlaylistReference
from infra.db.playlist_repository import PlaylistRepository
from infra.parsers.m3u_parser import M3UParser

logger = logging.getLogger(__name__)


class PlaylistService:
    def __init__(self, repository: PlaylistRepository):
        self.repository = repository
        self._current_playlist: Optional[Playlist] = None

    @property
    def current_playlist(self) -> Optional[Playlist]:
        return self._current_playlist

    def load_playlist(self, path: str, is_url: bool = False) -> Playlist:
        if not path:
            raise ValidationError("Playlist source is required")

        normalized = path.strip()
        if is_url:
            logger.info("Loading playlist from URL: %s", normalized)
            return self._load_from_url(normalized)

        return self._load_from_file(normalized)

    def _load_from_file(self, path: str) -> Playlist:
        try:
            playlist = M3UParser.parse(path)
        except FileNotFoundError as exc:
            logger.error("Playlist file not found: %s", path)
            raise
        except Exception as exc:  # pragma: no cover - parser wraps as ParsingError
            logger.error("Playlist parsing failed for %s: %s", path, exc)
            raise ParsingError(f"Failed to parse playlist: {path}") from exc

        playlist.source_path = os.path.abspath(path)
        self._current_playlist = playlist
        return playlist

    def _load_from_url(self, url: str) -> Playlist:
        tmp_path: Path | None = None
        try:
            content = self._download_with_retries(url, max_retries=3)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".m3u8") as tmp_file:
                tmp_path = Path(tmp_file.name)
                tmp_file.write(content)

            playlist = M3UParser.parse(str(tmp_path))
            playlist.source_path = url
            self._current_playlist = playlist
            return playlist
        except NetworkError:
            raise
        except Timeout as exc:
            raise NetworkError(f"Timed out while downloading playlist: {url}") from exc
        except RequestException as exc:
            raise NetworkError(f"Failed to download playlist: {url}") from exc
        except ParsingError:
            raise
        except Exception as exc:  # pragma: no cover - fallback
            logger.error("Unexpected playlist URL load failure (%s): %s", url, exc)
            raise ParsingError(f"Failed to load playlist from URL: {url}") from exc
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink()
                except OSError as exc:
                    logger.warning("Could not remove temporary playlist file %s: %s", tmp_path, exc)

    def _download_with_retries(self, url: str, max_retries: int = 3) -> bytes:
        if not url.lower().startswith(("http://", "https://")):
            raise ValidationError(f"Invalid playlist URL: {url}")

        last_error: Optional[Exception] = None
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(url, timeout=20)
                response.raise_for_status()
                return response.content
            except Timeout as exc:
                logger.warning("Playlist download timeout (%s/%s): %s", attempt, max_retries, url)
                last_error = exc
            except RequestException as exc:
                logger.warning("Playlist download error (%s/%s): %s", attempt, max_retries, exc)
                last_error = exc
            if attempt < max_retries:
                continue
        if isinstance(last_error, Timeout):
            raise NetworkError(f"Timed out while downloading playlist: {url}") from last_error
        raise NetworkError(f"Failed to download playlist: {url}") from last_error

    def save_playlist_reference(self, reference: PlaylistReference) -> None:
        self.repository.upsert_playlist(reference)

    def remove_playlist_reference(self, path: str) -> None:
        self.repository.delete_playlist(path)

    def get_saved_playlists(self) -> List[PlaylistReference]:
        return self.repository.get_playlists()

    def import_playlists(self, playlists: List[PlaylistReference]) -> None:
        self.repository.import_playlists(playlists)
