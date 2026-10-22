class MainController:
    def __init__(self, playlist_controller, settings_controller):
        self.playlist_controller = playlist_controller
        self.settings_controller = settings_controller

    def start(self) -> None:
        last_identity = self.settings_controller.get_setting("last_playlist_identity", "")
        if last_identity:
            saved_reference = self.playlist_controller.get_saved_playlist_by_identity(last_identity)
            if saved_reference is not None:
                self.playlist_controller.load_playlist(saved_reference)
