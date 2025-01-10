"""
This module contains the PlaylistController class, 
which is responsible for loading and displaying the playlist data.
"""

import os
import tempfile
import requests
from models.playlist import Playlist
from utils.m3u_parser import M3UParser
from views.notification import NotificationType


class PlaylistController:
    """Controller for managing playlists and updating the UI."""

    def __init__(self, main_window, settings_controller):
        self.window = main_window
        self.settings = settings_controller
        self.playlist = Playlist()

    def load_playlist_from_path(self, path: str, is_url: bool = False) -> bool:
        """Load a playlist from a file path or URL."""
        tmp_path = None
        try:
            if is_url:
                # Download playlist from URL
                response = requests.get(path, timeout=30)
                response.raise_for_status()

                # Save to temporary file
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".m3u8"
                ) as tmp_file:
                    tmp_file.write(response.content)
                    tmp_path = tmp_file.name

                # Parse the temporary file
                self.playlist = M3UParser.parse(tmp_path)
            else:
                # Parse local file
                self.playlist = M3UParser.parse(path)

            # Save settings
            self.settings.save_setting("last_playlist", path)
            self.settings.save_setting("last_playlist_is_url", str(is_url).lower())

            self._update_ui()
            return True

        except Exception as e:
            self.window.show_notification(
                f"Failed to load playlist: {str(e)}", NotificationType.ERROR
            )
            return False

        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    def _update_ui(self):
        """Update UI elements after playlist changes."""
        self._update_categories()
        self._update_channel_list()

    def _update_categories(self):
        """Update category combo box."""
        self.window.category_combo.clear()
        self.window.category_combo.addItem("All")
        self.window.category_combo.addItems(self.playlist.categories)

    def _update_channel_list(self):
        """Update channel list based on selected category."""
        category = self.window.category_combo.currentText()
        self.window.channel_list.clear()

        channels = (
            self.playlist.channels
            if category == "All"
            else self.playlist.get_channels_by_category(category)
        )

        for channel in channels:
            self.window.channel_list.addItem(channel.name)

    def refresh_channels(self):
        """Update the channel list display based on current category and filters."""
        self._update_channel_list()
