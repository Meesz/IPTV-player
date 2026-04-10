import logging
import os
import tempfile
from concurrent.futures import CancelledError
from pathlib import Path
from typing import Callable, Iterable, List, Optional
from urllib.parse import urlparse

import requests
from requests.exceptions import RequestException, Timeout

from core.errors import NetworkError, ParsingError, ValidationError
from core.models import Channel, ChannelQuery, Playlist, PlaylistReference
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

    def load_playlist(
        self,
        path: str,
        is_url: bool = False,
        *,
        progress_callback: Callable[[str], None] | None = None,
        cancel_callback: Callable[[], bool] | None = None,
        update_current: bool = True,
    ) -> Playlist:
        if not path:
            raise ValidationError("Playlist source is required")

        normalized = self._normalize_source(path, is_url)
        if is_url:
            logger.info("Loading playlist from URL: %s", normalized)
            return self._load_from_url(
                normalized,
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
                update_current=update_current,
            )

        return self._load_from_file(
            normalized,
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
            update_current=update_current,
        )

    def _load_from_file(
        self,
        path: str,
        *,
        progress_callback: Callable[[str], None] | None = None,
        cancel_callback: Callable[[], bool] | None = None,
        update_current: bool = True,
    ) -> Playlist:
        self._ensure_not_cancelled(cancel_callback)
        self._emit_progress(progress_callback, "Parsing playlist")
        try:
            playlist = M3UParser.parse(path)
        except FileNotFoundError as exc:
            logger.error("Playlist file not found: %s", path)
            raise
        except Exception as exc:  # pragma: no cover - parser wraps as ParsingError
            logger.error("Playlist parsing failed for %s: %s", path, exc)
            raise ParsingError(f"Failed to parse playlist: {path}") from exc

        playlist.source_path = os.path.abspath(path)
        self._apply_source_path(playlist)
        self._ensure_not_cancelled(cancel_callback)
        if update_current:
            self._current_playlist = playlist
        return playlist

    def _load_from_url(
        self,
        url: str,
        *,
        progress_callback: Callable[[str], None] | None = None,
        cancel_callback: Callable[[], bool] | None = None,
        update_current: bool = True,
    ) -> Playlist:
        tmp_path: Path | None = None
        try:
            self._ensure_not_cancelled(cancel_callback)
            self._emit_progress(progress_callback, "Downloading playlist")
            content = self._download_with_retries(url, max_retries=3)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".m3u8") as tmp_file:
                tmp_path = Path(tmp_file.name)
                tmp_file.write(content)

            self._ensure_not_cancelled(cancel_callback)
            self._emit_progress(progress_callback, "Parsing playlist")
            playlist = M3UParser.parse(str(tmp_path))
            playlist.source_path = url
            self._apply_source_path(playlist)
            self._ensure_not_cancelled(cancel_callback)
            if update_current:
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
        if not self._is_valid_url(url):
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
        self.repository.upsert_playlist(self._normalize_reference(reference))

    def remove_playlist_reference(self, path: str) -> None:
        normalized_path = self._normalize_source(
            path,
            path.startswith(("http://", "https://")),
        )
        self.repository.delete_playlist(normalized_path)

    def get_saved_playlists(self) -> List[PlaylistReference]:
        return self.repository.get_playlists()

    def query_channels(self, playlist: Playlist, query: ChannelQuery) -> list[Channel]:
        selected_category = query.category or "All"
        search_text = query.text.strip().lower()

        if selected_category == "All":
            channels = list(playlist.channels)
        else:
            channels = list(playlist.get_channels_by_category(selected_category))

        if search_text:
            if not query.current_category_only:
                channels = list(playlist.channels)
            channels = [
                channel
                for channel in channels
                if search_text in channel.name.lower()
                or search_text in channel.group.lower()
            ]

        return self._sort_channels(channels, query.sort_mode, query.favorite_keys)

    def search_channels(
        self,
        query: str,
        *,
        playlist: Playlist | None = None,
        category: str = "All",
        current_category_only: bool = True,
        sort_mode: str = "name_asc",
        favorite_keys: set[tuple[str, str]] | None = None,
    ) -> list[Channel]:
        target_playlist = playlist or self._current_playlist
        if not target_playlist:
            return []
        return self.query_channels(
            target_playlist,
            ChannelQuery(
                category=category,
                text=query,
                current_category_only=current_category_only,
                sort_mode=sort_mode,
                favorite_keys=favorite_keys or set(),
            ),
        )

    def set_current_playlist(self, playlist: Playlist) -> None:
        self._current_playlist = playlist

    def import_playlists(
        self,
        playlists: List[PlaylistReference],
        *,
        active_playlist_path: str = "",
    ) -> None:
        current_playlists = self.repository.get_playlists()
        normalized_playlists = self._normalize_references(playlists)
        if active_playlist_path:
            normalized_active_path = self._normalize_source(
                active_playlist_path,
                active_playlist_path.startswith(("http://", "https://")),
            )
            current_paths = {item.path for item in current_playlists}
            next_paths = {item.path for item in normalized_playlists}
            if normalized_active_path in current_paths and normalized_active_path not in next_paths:
                raise ValidationError("Cannot remove the active playlist from the library")
        self.repository.import_playlists(normalized_playlists)

    def get_saved_playlist(self, path: str) -> PlaylistReference | None:
        normalized_path = self._normalize_source(
            path,
            path.startswith(("http://", "https://")),
        )
        return self.repository.get_playlist(normalized_path)

    def update_playlist_metadata(
        self,
        path: str,
        *,
        channel_count: int,
        last_loaded_at: str,
        last_status: str,
        last_error: str = "",
    ) -> None:
        self.repository.update_playlist_metadata(
            self._normalize_source(path, path.startswith(("http://", "https://"))),
            channel_count=channel_count,
            last_loaded_at=last_loaded_at,
            last_status=last_status,
            last_error=last_error,
        )

    def validate_playlist_reference(
        self,
        reference: PlaylistReference,
        *,
        existing_keys: set[tuple[str, bool]] | None = None,
    ) -> PlaylistReference:
        normalized = self._normalize_reference(reference)
        if existing_keys is not None:
            key = (normalized.path, normalized.is_url)
            if key in existing_keys:
                source = "URL" if normalized.is_url else "file"
                raise ValidationError(f"Duplicate playlist {source}: {normalized.path}")
            existing_keys.add(key)
        return normalized

    def probe_playlist_reference(
        self,
        reference: PlaylistReference,
        *,
        progress_callback: Callable[[str], None] | None = None,
        cancel_callback: Callable[[], bool] | None = None,
    ) -> PlaylistReference:
        normalized = self.validate_playlist_reference(reference)
        playlist = self.load_playlist(
            normalized.path,
            normalized.is_url,
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
            update_current=False,
        )
        return PlaylistReference(
            name=normalized.name,
            path=normalized.path,
            is_url=normalized.is_url,
            channel_count=len(playlist.channels),
            last_loaded_at=normalized.last_loaded_at,
            last_status="warning" if playlist.parse_warnings else "ready",
            last_error=playlist.parse_warnings[0].message if playlist.parse_warnings else "",
        )

    def _normalize_references(self, playlists: Iterable[PlaylistReference]) -> List[PlaylistReference]:
        seen_keys: set[tuple[str, bool]] = set()
        normalized: List[PlaylistReference] = []
        for playlist in playlists:
            normalized.append(
                self.validate_playlist_reference(playlist, existing_keys=seen_keys)
            )
        return normalized

    def _normalize_reference(self, reference: PlaylistReference) -> PlaylistReference:
        name = reference.name.strip()
        if not name:
            raise ValidationError("Playlist name is required")

        path = self._normalize_source(reference.path, reference.is_url)
        if reference.is_url:
            if not self._is_valid_url(path):
                raise ValidationError(f"Invalid playlist URL: {path}")
        else:
            path_obj = Path(path)
            if not path_obj.exists():
                raise ValidationError(f"Playlist file not found: {path}")
            if not path_obj.is_file():
                raise ValidationError(f"Playlist path is not a file: {path}")

        return PlaylistReference(
            name=name,
            path=path,
            is_url=reference.is_url,
            channel_count=reference.channel_count,
            last_loaded_at=reference.last_loaded_at,
            last_status=reference.last_status,
            last_error=reference.last_error,
        )

    @staticmethod
    def _normalize_source(path: str, is_url: bool) -> str:
        normalized = path.strip()
        if not normalized:
            raise ValidationError("Playlist source is required")
        if is_url:
            return normalized
        return str(Path(normalized).expanduser().resolve())

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def _apply_source_path(playlist: Playlist) -> None:
        for channel in playlist.channels:
            channel.playlist_path = playlist.source_path

    @staticmethod
    def _emit_progress(
        callback: Callable[[str], None] | None,
        message: str,
    ) -> None:
        if callback is not None:
            callback(message)

    @staticmethod
    def _ensure_not_cancelled(callback: Callable[[], bool] | None) -> None:
        if callback is not None and callback():
            raise CancelledError("Playlist load cancelled")

    @staticmethod
    def _sort_channels(
        channels: list[Channel],
        sort_mode: str,
        favorite_keys: set[tuple[str, str]],
    ) -> list[Channel]:
        if sort_mode == "name_desc":
            return sorted(channels, key=lambda item: item.name.lower(), reverse=True)
        if sort_mode == "group":
            return sorted(channels, key=lambda item: (item.group.lower(), item.name.lower()))
        if sort_mode == "favorites_first":
            return sorted(
                channels,
                key=lambda item: (item.identity_key() not in favorite_keys, item.name.lower()),
            )
        return sorted(channels, key=lambda item: item.name.lower())
