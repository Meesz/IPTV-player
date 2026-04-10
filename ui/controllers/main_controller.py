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
                return

        last_source = self.settings_controller.get_setting("last_playlist_source_type", "")
        last_playlist = self.settings_controller.get_setting("last_playlist_path", "") or self.settings_controller.get_setting("last_playlist", "")
        last_playlist_is_url = str(
            self.settings_controller.get_setting("last_playlist_is_url", "false")
        ).strip().lower()
        is_url = last_source == "url" or last_playlist_is_url in {"1", "true", "yes", "on"}
        if last_playlist_is_url not in {"1", "true", "yes", "on", "0", "false", "no", "off"}:
            is_url = str(last_playlist).startswith(("http://", "https://"))
        if last_playlist:
            self.playlist_controller.load_playlist(last_playlist, is_url)
