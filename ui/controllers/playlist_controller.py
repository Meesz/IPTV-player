from PyQt6.QtCore import QObject, pyqtSignal
from core.models import Playlist, Channel
from core.services.playlist_service import PlaylistService

class PlaylistController(QObject):
    playlist_loaded = pyqtSignal(Playlist)
    error_occurred = pyqtSignal(str)

    def __init__(self, service: PlaylistService):
        super().__init__()
        self.service = service

    def load_playlist(self, path: str, is_url: bool = False):
        try:
            playlist = self.service.load_playlist(path, is_url)
            self.playlist_loaded.emit(playlist)
            return True
        except Exception as e:
            self.error_occurred.emit(str(e))
            return False

    def get_current_playlist(self) -> Playlist:
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

    def save_playlist_ref(self, name: str, path: str, is_url: bool):
        self.service.save_playlist_ref(name, path, is_url)

    def get_saved_playlists(self):
        return self.service.get_saved_playlists()
