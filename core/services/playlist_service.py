import os
import tempfile
import logging
import requests
from requests.exceptions import RequestException, Timeout
from typing import Optional, List, Tuple
from core.models import Playlist
from infra.parsers.m3u_parser import M3UParser
from infra.db.playlist_repository import PlaylistRepository

logger = logging.getLogger(__name__)

class PlaylistService:
    def __init__(self, repository: PlaylistRepository):
        self.repository = repository
        self._current_playlist: Optional[Playlist] = None

    @property
    def current_playlist(self) -> Optional[Playlist]:
        return self._current_playlist

    def load_playlist(self, path: str, is_url: bool = False, max_retries: int = 3) -> Playlist:
        """Load a playlist from a file path or URL."""
        if is_url:
            self._current_playlist = self._download_and_parse_playlist(path, max_retries)
        else:
            logger.info(f"Loading playlist from local file: {path}")
            self._current_playlist = M3UParser.parse(path)
        
        return self._current_playlist

    def _download_and_parse_playlist(self, url: str, max_retries: int) -> Playlist:
        logger.info(f"Downloading playlist from URL: {url}")
        content = self._download_with_retries(url, max_retries)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".m3u8") as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name

        try:
            logger.info("Parsing downloaded playlist")
            return M3UParser.parse(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except Exception as e:
                logger.warning(f"Failed to remove temporary file: {str(e)}")

    def _download_with_retries(self, url: str, max_retries: int) -> bytes:
        for attempt in range(max_retries):
            try:
                logger.debug(f"Download attempt {attempt + 1}/{max_retries}")
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                return response.content
            except Timeout:
                if attempt < max_retries - 1:
                    logger.warning(f"Timeout, retrying ({attempt + 1}/{max_retries})")
                    continue
                raise TimeoutError(f"Timed out downloading playlist after {max_retries} attempts")
            except RequestException as e:
                raise RuntimeError(f"Error downloading playlist: {str(e)}")
        raise RuntimeError("Unexpected error in download retry logic")

    def save_playlist_ref(self, name: str, path: str, is_url: bool):
        """Save a reference to the playlist in the DB."""
        # This is a bit simplistic, assuming we just append or overwrite.
        # For now, let's just use the repository to save the current list.
        # But wait, the repository saves a list of playlists.
        # We need to fetch existing, add/update, and save back.
        playlists = self.repository.get_playlists()
        # Remove existing if same path
        playlists = [p for p in playlists if p[1] != path]
        playlists.append((name, path, is_url))
        self.repository.save_playlists(playlists)

    def get_saved_playlists(self) -> List[Tuple[str, str, bool]]:
        return self.repository.get_playlists()
