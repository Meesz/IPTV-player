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
from PyQt6.QtWidgets import QApplication


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
            print(f"\nLoading playlist from: {'URL' if is_url else 'File'} - {path}")
            if is_url:
                print("Downloading playlist from URL...")
                response = requests.get(path, timeout=30)
                response.raise_for_status()

                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".m3u8"
                ) as tmp_file:
                    tmp_file.write(response.content)
                    tmp_path = tmp_file.name

                print("Parsing downloaded playlist...")
                self.playlist = M3UParser.parse(tmp_path)
            else:
                print("Parsing local playlist file...")
                self.playlist = M3UParser.parse(path)

            print("\nLoaded channels:")
            for channel in self.playlist.channels:
                print(f"Channel: {channel.name} - URL: {channel.url}")
            print(f"Total channels loaded: {len(self.playlist.channels)}\n")

            # Save settings
            print("Saving playlist settings...")
            self.settings.save_setting("last_playlist", path)
            self.settings.save_setting("last_playlist_is_url", str(is_url).lower())

            # Update UI in smaller chunks
            print("Updating UI...")
            self._update_ui_safely()
            print("Playlist loading completed successfully")
            return True

        except Exception as e:
            print(f"Error loading playlist: {str(e)}")
            self.window.show_notification(
                f"Failed to load playlist: {str(e)}", NotificationType.ERROR
            )
            return False

        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception as e:
                    print(f"Failed to cleanup temporary file: {e}")

    def _update_ui_safely(self):
        """Update UI elements after playlist changes with progress logging."""
        try:
            print("Updating categories...")
            self._update_categories()
            
            print("Updating channel list...")
            self._update_channel_list()
            
            print("UI update completed")
            self.window.show_notification(
                f"Loaded {len(self.playlist.channels)} channels successfully",
                NotificationType.SUCCESS
            )
        except Exception as e:
            print(f"Error during UI update: {str(e)}")
            self.window.show_notification(
                f"Error updating UI: {str(e)}", 
                NotificationType.ERROR
            )

    def _update_categories(self):
        """Update category combo box."""
        self.window.category_combo.clear()
        self.window.category_combo.addItem("All")
        self.window.category_combo.addItems(self.playlist.categories)

    def _update_channel_list(self):
        """Update channel list based on selected category."""
        try:
            category = self.window.category_combo.currentText()
            self.window.channel_list.clear()

            # Get channels for the selected category
            channels = (
                self.playlist.channels
                if category == "All"
                else self.playlist.get_channels_by_category(category)
            )

            # Add channels in smaller batches to prevent UI freezing
            batch_size = 100
            total_channels = len(channels)
            
            for i in range(0, total_channels, batch_size):
                batch = channels[i:i + batch_size]
                for channel in batch:
                    self.window.channel_list.addItem(channel.name)
                print(f"Added channels {i} to {min(i + batch_size, total_channels)} of {total_channels}")
                QApplication.processEvents()  # Allow UI to update

        except Exception as e:
            print(f"Error updating channel list: {str(e)}")
            raise

    def refresh_channels(self):
        """Update the channel list display based on current category and filters."""
        self._update_channel_list()
