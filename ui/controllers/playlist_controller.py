from PyQt6.QtCore import QObject, pyqtSignal

from pathlib import Path

from core.errors import NetworkError, ParsingError, RepositoryError, ValidationError
from core.models import Playlist, PlaylistReference
from core.services.playlist_service import PlaylistService

class PlaylistController(QObject):
    playlist_loaded = pyqtSignal(Playlist)
    error_occurred = pyqtSignal(str)
    loading_started = pyqtSignal()
    loading_finished = pyqtSignal()

    def __init__(self, service: PlaylistService):
        super().__init__()
        self.service = service

    def load_playlist(self, path: str, is_url: bool = False):
        try:
            self.loading_started.emit()
            playlist = self.service.load_playlist(path, is_url)
            self.playlist_loaded.emit(playlist)
            return True
        except (
            NetworkError,
            ParsingError,
            ValidationError,
            RepositoryError,
            OSError,
            ValueError,
        ) as exc:
            self.error_occurred.emit(str(exc))
            return False
        finally:
            self.loading_finished.emit()

    def get_current_playlist(self) -> Playlist | None:
        return self.service.current_playlist

    def get_channels_by_category(self, category: str):
        if self.service.current_playlist:
            if category == "All":
                return self.service.current_playlist.channels
            return self.service.current_playlist.get_channels_by_category(category)
        return []

    def search_channels(self, query: str):
        if self.service.current_playlist:
            # Simple search implementation
            query = query.lower()
            return [c for c in self.service.current_playlist.channels if query in c.name.lower()]
        return []

    def save_playlist_reference(self, reference: PlaylistReference | str, is_url: bool | None = None) -> None:
        if isinstance(reference, str):
            if is_url is None:
                raise ValueError("is_url must be provided when passing a path")
            reference = PlaylistReference(name=Path(reference).name or "Playlist", path=reference, is_url=is_url)
        self.service.save_playlist_reference(reference)

    def get_saved_playlists(self):
        return self.service.get_saved_playlists()

    def remove_saved_playlist(self, path: str) -> None:
        self.service.remove_playlist_reference(path)

    def import_playlists(self, playlists: list[PlaylistReference]) -> None:
        try:
            self.service.import_playlists(playlists)
            return None
        except Exception as exc:
            self.error_occurred.emit(str(exc))
            return None
