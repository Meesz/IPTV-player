from PyQt6.QtCore import QObject
from ui.controllers.playlist_controller import PlaylistController
from ui.controllers.epg_controller import EPGController
from ui.controllers.settings_controller import SettingsController

class MainController(QObject):
    def __init__(self, 
                 playlist_controller: PlaylistController,
                 epg_controller: EPGController,
                 settings_controller: SettingsController):
        super().__init__()
        self.playlist_controller = playlist_controller
        self.epg_controller = epg_controller
        self.settings_controller = settings_controller

    def start(self):
        # Load last playlist if available
        last_playlist = self.settings_controller.get_setting("last_playlist")
        is_url = self.settings_controller.get_setting("last_playlist_is_url") == "True"
        
        if last_playlist:
            self.playlist_controller.load_playlist(last_playlist, is_url)
