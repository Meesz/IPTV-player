import logging
import os
import tempfile
import time
from collections.abc import Callable, Iterable
from concurrent.futures import CancelledError
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.exceptions import HTTPError, RequestException, Timeout

from core import limits
from core.bounded_download import USER_AGENT, read_bounded
from core.errors import NetworkError, ParsingError, ValidationError
from core.models import Channel, ChannelQuery, Playlist, PlaylistReference, PlaylistSourceType
from core.redaction import redact_identity, redact_text, redact_url
from infra.db.playlist_repository import PlaylistRepository
from infra.parsers.m3u_parser import M3UParser
from infra.providers.xtream_client import XtreamClient

logger = logging.getLogger(__name__)

# Delay before retry n is BASE * FACTOR ** (n - 1): 0.5 s, then 1 s with three attempts.
RETRY_BACKOFF_BASE_SECONDS = 0.5
RETRY_BACKOFF_FACTOR = 2
# Client errors that may clear up on their own: Request Timeout and Too Many Requests.
_TRANSIENT_CLIENT_ERRORS = frozenset({408, 429})
# Module-level hook so tests can avoid real delays.
_sleep = time.sleep


class PlaylistService:
    def __init__(
        self,
        repository: PlaylistRepository,
        *,
        xtream_client: XtreamClient | None = None,
    ):
        self.repository = repository
        self.xtream_client = xtream_client or XtreamClient()
        self._current_playlist: Playlist | None = None

    @property
    def current_playlist(self) -> Playlist | None:
        return self._current_playlist

    def load_playlist(
        self,
        source: PlaylistReference | str,
        is_url: bool = False,
        *,
        progress_callback: Callable[[str], None] | None = None,
        cancel_callback: Callable[[], bool] | None = None,
        update_current: bool = True,
    ) -> Playlist:
        reference = self._resolve_reference(source, is_url=is_url)
        normalized = self._normalize_reference(reference)
        logger.info(
            "Loading playlist source type=%s identity=%s",
            normalized.source_type.value,
            redact_identity(normalized.source_identity),
        )

        if normalized.source_type == PlaylistSourceType.FILE:
            playlist = self._load_from_file(
                normalized,
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
                update_current=update_current,
            )
        elif normalized.source_type == PlaylistSourceType.URL:
            playlist = self._load_from_url(
                normalized,
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
                update_current=update_current,
            )
        else:
            playlist = self._load_from_xtream(
                normalized,
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
                update_current=update_current,
            )

        final_reference = playlist.source_reference or normalized
        playlist.source_reference = final_reference
        playlist.source_path = final_reference.source_identity
        playlist.name = final_reference.display_label()
        self._apply_source_path(playlist)
        if update_current:
            self._current_playlist = playlist
        logger.info(
            "Playlist load completed type=%s identity=%s channels=%s",
            final_reference.source_type.value,
            redact_identity(final_reference.source_identity),
            len(playlist.channels),
        )
        return playlist

    def save_playlist_reference(self, reference: PlaylistReference) -> None:
        self.repository.upsert_playlist(self._normalize_reference(reference))

    def remove_playlist_reference(
        self,
        source: PlaylistReference | str,
        is_url: bool | None = None,
    ) -> None:
        reference = self._resolve_reference(source, is_url=is_url)
        self.repository.delete_playlist(self._normalize_reference(reference).source_identity)

    def get_saved_playlists(self) -> list[PlaylistReference]:
        return self.repository.get_playlists()

    def get_saved_playlist_by_identity(self, identity: str) -> PlaylistReference | None:
        return self.repository.get_playlist_by_identity(identity)

    def get_saved_playlist(
        self,
        source: PlaylistReference | str,
        is_url: bool | None = None,
    ) -> PlaylistReference | None:
        reference = self._resolve_reference(source, is_url=is_url)
        return self.repository.get_playlist_by_identity(self._normalize_reference(reference).source_identity)

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
                if search_text in channel.name.lower() or search_text in channel.group.lower()
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
        playlists: list[PlaylistReference],
        *,
        active_playlist_path: str = "",
    ) -> None:
        current_playlists = self.repository.get_playlists()
        normalized_playlists = self._normalize_references(playlists)
        if active_playlist_path:
            current_paths = {item.source_identity for item in current_playlists}
            next_paths = {item.source_identity for item in normalized_playlists}
            if active_playlist_path in current_paths and active_playlist_path not in next_paths:
                raise ValidationError("Cannot remove the active playlist from the library")
        self.repository.import_playlists(normalized_playlists)

    def update_playlist_metadata(
        self,
        source: PlaylistReference | str,
        *,
        channel_count: int,
        last_loaded_at: str,
        last_status: str,
        last_error: str = "",
        is_url: bool | None = None,
    ) -> None:
        reference = self._resolve_reference(source, is_url=is_url)
        self.repository.update_playlist_metadata(
            self._normalize_reference(reference).source_identity,
            channel_count=channel_count,
            last_loaded_at=last_loaded_at,
            last_status=last_status,
            last_error=last_error,
        )

    def validate_playlist_reference(
        self,
        reference: PlaylistReference,
        *,
        existing_keys: set[tuple[str, ...]] | None = None,
    ) -> PlaylistReference:
        normalized = self._normalize_reference(reference)
        if existing_keys is not None:
            key = normalized.identity_key()
            if key in existing_keys:
                source = normalized.source_type.value.upper()
                summary = normalized.source_summary()
                if normalized.source_type == PlaylistSourceType.URL:
                    summary = redact_url(summary)
                raise ValidationError(f"Duplicate playlist {source}: {summary}")
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
            normalized,
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
            update_current=False,
        )
        xtream = (
            normalized.normalized_xtream() if normalized.source_type == PlaylistSourceType.XTREAM else normalized.xtream
        )
        return PlaylistReference(
            name=normalized.name,
            path=normalized.path if normalized.source_type != PlaylistSourceType.FILE else normalized.normalized_path(),
            source_type=normalized.source_type,
            xtream=xtream,
            channel_count=len(playlist.channels),
            last_loaded_at=normalized.last_loaded_at,
            last_status="warning" if playlist.parse_warnings else "ready",
            last_error=playlist.parse_warnings[0].message if playlist.parse_warnings else "",
        )

    def build_legacy_reference(self, path: str, is_url: bool = False) -> PlaylistReference:
        normalized_path = self._normalize_source(path, is_url)
        name = "URL Playlist" if is_url else Path(normalized_path).name or "Playlist"
        return PlaylistReference(
            name=name,
            path=normalized_path,
            source_type=PlaylistSourceType.URL if is_url else PlaylistSourceType.FILE,
        )

    def _load_from_file(
        self,
        reference: PlaylistReference,
        *,
        progress_callback: Callable[[str], None] | None = None,
        cancel_callback: Callable[[], bool] | None = None,
        update_current: bool = True,
    ) -> Playlist:
        path = reference.normalized_path()
        self._ensure_not_cancelled(cancel_callback)
        self._emit_progress(progress_callback, "Parsing playlist")
        try:
            playlist = M3UParser.parse(path)
        except FileNotFoundError:
            logger.error("Playlist file not found: %s", path)
            raise
        except Exception as exc:  # pragma: no cover - parser wraps as ParsingError
            logger.error("Playlist parsing failed for %s: %s", path, exc)
            raise ParsingError(f"Failed to parse playlist: {path}") from exc

        playlist.source_path = reference.source_identity
        playlist.source_reference = reference
        playlist.name = reference.display_label()
        self._ensure_not_cancelled(cancel_callback)
        if update_current:
            self._current_playlist = playlist
        return playlist

    def _load_from_url(
        self,
        reference: PlaylistReference,
        *,
        progress_callback: Callable[[str], None] | None = None,
        cancel_callback: Callable[[], bool] | None = None,
        update_current: bool = True,
    ) -> Playlist:
        url = reference.normalized_url()
        tmp_path: Path | None = None
        try:
            self._ensure_not_cancelled(cancel_callback)
            self._emit_progress(progress_callback, "Downloading playlist")
            content = self._download_with_retries(url, max_retries=3, cancel_callback=cancel_callback)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".m3u8") as tmp_file:
                tmp_path = Path(tmp_file.name)
                tmp_file.write(content)

            self._ensure_not_cancelled(cancel_callback)
            self._emit_progress(progress_callback, "Parsing playlist")
            playlist = M3UParser.parse(str(tmp_path))
            playlist.source_path = reference.source_identity
            playlist.source_reference = reference
            playlist.name = reference.display_label()
            self._ensure_not_cancelled(cancel_callback)
            if update_current:
                self._current_playlist = playlist
            return playlist
        except NetworkError:
            raise
        except Timeout as exc:
            raise NetworkError(f"Timed out while downloading playlist: {redact_url(url)}") from exc
        except RequestException as exc:
            raise NetworkError(f"Failed to download playlist: {redact_url(url)}") from exc
        except ParsingError:
            raise
        except CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - fallback
            logger.error("Unexpected playlist URL load failure (%s): %s", redact_url(url), redact_text(str(exc)))
            raise ParsingError(f"Failed to load playlist from URL: {redact_url(url)}") from exc
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink()
                except OSError as exc:
                    logger.warning("Could not remove temporary playlist file %s: %s", tmp_path, exc)

    def _load_from_xtream(
        self,
        reference: PlaylistReference,
        *,
        progress_callback: Callable[[str], None] | None = None,
        cancel_callback: Callable[[], bool] | None = None,
        update_current: bool = True,
    ) -> Playlist:
        credentials = reference.normalized_xtream()
        effective_credentials = credentials
        logger.info(
            "Starting Xtream playlist load for %s",
            credentials.redacted_summary(),
        )
        self._ensure_not_cancelled(cancel_callback)
        self._emit_progress(progress_callback, "Authenticating Xtream source")
        try:
            self.xtream_client.validate_credentials(credentials)
            effective_credentials = self.xtream_client.last_effective_credentials or credentials
            logger.debug(
                "Xtream authentication phase succeeded for %s",
                effective_credentials.redacted_summary(),
            )
        except (ValidationError, NetworkError, ParsingError):
            logger.exception(
                "Xtream authentication phase failed for %s",
                credentials.redacted_summary(),
            )
            raise
        self._ensure_not_cancelled(cancel_callback)
        self._emit_progress(progress_callback, "Fetching Xtream live channels")
        try:
            channels = self.xtream_client.fetch_live_channels(effective_credentials)
            effective_credentials = self.xtream_client.last_effective_credentials or effective_credentials
        except (ValidationError, NetworkError, ParsingError):
            logger.exception(
                "Xtream live channel fetch failed for %s",
                effective_credentials.redacted_summary(),
            )
            raise
        logger.info(
            "Xtream live channel fetch succeeded for %s with %s channels",
            effective_credentials.redacted_summary(),
            len(channels),
        )
        effective_reference = PlaylistReference(
            name=reference.name,
            path="",
            source_type=PlaylistSourceType.XTREAM,
            xtream=effective_credentials,
            channel_count=reference.channel_count,
            last_loaded_at=reference.last_loaded_at,
            last_status=reference.last_status,
            last_error=reference.last_error,
        )
        playlist = Playlist(
            name=reference.display_label(),
            source_path=effective_reference.source_identity,
            source_reference=effective_reference,
            channels=channels,
        )
        self._ensure_not_cancelled(cancel_callback)
        if update_current:
            self._current_playlist = playlist
        return playlist

    @staticmethod
    def _is_permanent_http_error(exc: HTTPError) -> bool:
        """4xx responses (except 408/429) will not change on retry."""
        status = getattr(exc.response, "status_code", None)
        return isinstance(status, int) and 400 <= status < 500 and status not in _TRANSIENT_CLIENT_ERRORS

    def _download_with_retries(
        self,
        url: str,
        max_retries: int = 3,
        cancel_callback: Callable[[], bool] | None = None,
    ) -> bytes:
        if not self._is_valid_url(url):
            raise ValidationError(f"Invalid playlist URL: {redact_url(url)}")

        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(url, timeout=20, stream=True, headers={"User-Agent": USER_AGENT})
                try:
                    response.raise_for_status()
                except BaseException:
                    response.close()
                    raise
                return read_bounded(
                    response,
                    max_bytes=limits.MAX_PLAYLIST_DOWNLOAD_BYTES,
                    deadline_seconds=limits.PLAYLIST_DOWNLOAD_DEADLINE_SECONDS,
                    description="Playlist download",
                )
            except NetworkError:
                # Over-budget or too slow: retrying cannot help.
                raise
            except Timeout as exc:
                logger.warning("Playlist download timeout (%s/%s): %s", attempt, max_retries, redact_url(url))
                last_error = exc
            except RequestException as exc:
                logger.warning("Playlist download error (%s/%s): %s", attempt, max_retries, redact_text(str(exc)))
                last_error = exc
                if isinstance(exc, HTTPError) and self._is_permanent_http_error(exc):
                    break
            if attempt < max_retries:
                self._ensure_not_cancelled(cancel_callback)
                _sleep(RETRY_BACKOFF_BASE_SECONDS * RETRY_BACKOFF_FACTOR ** (attempt - 1))
                self._ensure_not_cancelled(cancel_callback)
        if isinstance(last_error, Timeout):
            raise NetworkError(f"Timed out while downloading playlist: {redact_url(url)}") from last_error
        raise NetworkError(f"Failed to download playlist: {redact_url(url)}") from last_error

    def _normalize_references(self, playlists: Iterable[PlaylistReference]) -> list[PlaylistReference]:
        seen_keys: set[tuple[str, ...]] = set()
        normalized: list[PlaylistReference] = []
        for playlist in playlists:
            normalized.append(self.validate_playlist_reference(playlist, existing_keys=seen_keys))
        return normalized

    def _normalize_reference(self, reference: PlaylistReference) -> PlaylistReference:
        name = reference.name.strip()
        if not name:
            raise ValidationError("Playlist name is required")

        if reference.source_type == PlaylistSourceType.XTREAM:
            credentials = reference.normalized_xtream()
            if not credentials.server_url:
                raise ValidationError("Xtream server URL is required")
            if not self._is_valid_url(credentials.server_url):
                raise ValidationError("Xtream server URL must be a valid http or https URL")
            if not credentials.username:
                raise ValidationError("Xtream username is required")
            if not credentials.password:
                raise ValidationError("Xtream password is required")
            if credentials.output not in {"ts", "m3u8"}:
                raise ValidationError("Xtream output must be ts or m3u8")
            return PlaylistReference(
                name=name,
                path="",
                source_type=PlaylistSourceType.XTREAM,
                xtream=credentials,
                channel_count=reference.channel_count,
                last_loaded_at=reference.last_loaded_at,
                last_status=reference.last_status,
                last_error=reference.last_error,
            )

        path = self._normalize_source(reference.path, reference.source_type == PlaylistSourceType.URL)
        if reference.source_type == PlaylistSourceType.URL:
            if not self._is_valid_url(path):
                raise ValidationError(f"Invalid playlist URL: {redact_url(path)}")
        else:
            path_obj = Path(path)
            if not path_obj.exists():
                raise ValidationError(f"Playlist file not found: {path}")
            if not path_obj.is_file():
                raise ValidationError(f"Playlist path is not a file: {path}")

        return PlaylistReference(
            name=name,
            path=path,
            source_type=reference.source_type,
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
        return os.path.abspath(normalized)

    @staticmethod
    def _resolve_reference(
        source: PlaylistReference | str,
        *,
        is_url: bool | None = None,
    ) -> PlaylistReference:
        if isinstance(source, PlaylistReference):
            return source
        if is_url is None:
            is_url = source.startswith(("http://", "https://"))
        normalized_path = source.strip()
        return PlaylistReference(
            name="URL Playlist" if is_url else Path(normalized_path).name or "Playlist",
            path=normalized_path,
            source_type=PlaylistSourceType.URL if is_url else PlaylistSourceType.FILE,
        )

    @staticmethod
    def _is_valid_url(value: str) -> bool:
        parsed = urlparse(value.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def _emit_progress(callback: Callable[[str], None] | None, message: str) -> None:
        if callback is not None:
            callback(message)

    @staticmethod
    def _ensure_not_cancelled(cancel_callback: Callable[[], bool] | None) -> None:
        if cancel_callback and cancel_callback():
            raise CancelledError("Playlist load cancelled")

    @staticmethod
    def _apply_source_path(playlist: Playlist) -> None:
        for channel in playlist.channels:
            channel.playlist_path = playlist.source_path

    @staticmethod
    def _sort_channels(
        channels: list[Channel],
        sort_mode: str,
        favorite_keys: set[tuple[str, str]],
    ) -> list[Channel]:
        if sort_mode == "name_desc":
            return sorted(channels, key=lambda channel: channel.name.lower(), reverse=True)
        if sort_mode == "group":
            return sorted(
                channels,
                key=lambda channel: (
                    channel.group.lower(),
                    channel.channel_number or 0,
                    channel.name.lower(),
                ),
            )
        if sort_mode == "favorites_first":
            return sorted(
                channels,
                key=lambda channel: (
                    0 if channel.identity_key() in favorite_keys else 1,
                    channel.group.lower(),
                    channel.name.lower(),
                ),
            )
        return sorted(channels, key=lambda channel: channel.name.lower())
