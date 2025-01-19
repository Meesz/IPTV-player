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
from PyQt6.QtCore import QThreadPool
from utils.worker import Worker
from config import Config


class PlaylistController:
    """Controller for managing playlists and updating the UI."""

    def __init__(self, main_window, settings_controller):
        self.window = main_window
        self.settings = settings_controller
        self.playlist = Playlist()
        # Initialize thread pool
        self.threadpool = QThreadPool()
        self._is_updating = False  # Add update lock
        print(f"Multithreading with maximum {self.threadpool.maxThreadCount()} threads")

    def load_playlist_from_path(self, path: str, is_url: bool = False) -> None:
        """Load a playlist from a file path or URL."""
        print(f"\n=== Loading playlist from {'URL' if is_url else 'file'}: {path} ===")
        print(f"Called by: {__import__('traceback').extract_stack()[-2][2]}")  # Show caller
        
        # Show loading indicator
        self.window.show_notification("Loading playlist...", NotificationType.INFO)
        
        # Create worker for loading playlist
        worker = Worker(self._load_playlist_worker, path, is_url)
        
        # Connect signals
        worker.signals.result.connect(self._on_playlist_loaded)
        worker.signals.error.connect(self._on_playlist_error)
        
        # Execute
        self.threadpool.start(worker)

    def _load_playlist_worker(self, path: str, is_url: bool) -> tuple:
        """Worker function to load playlist in background."""
        tmp_path = None
        try:
            if is_url:
                print("Downloading playlist from URL...")
                response = requests.get(path, timeout=Config.REQUEST_TIMEOUT)
                response.raise_for_status()

                with tempfile.NamedTemporaryFile(delete=False, suffix=".m3u8") as tmp_file:
                    tmp_file.write(response.content)
                    tmp_path = tmp_file.name

                print("Parsing downloaded playlist...")
                playlist = M3UParser.parse(tmp_path)
            else:
                print("Parsing local playlist file...")
                playlist = M3UParser.parse(path)

            return (True, playlist, path, is_url)

        except Exception as e:
            return (False, str(e), None, None)

        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception as e:
                    print(f"Failed to cleanup temporary file: {e}")

    def _on_playlist_loaded(self, result):
        """Handle successful playlist loading."""
        success, data, path, is_url = result
        
        if success:
            # Check if this is a duplicate load
            if (hasattr(self, '_last_loaded_path') and 
                self._last_loaded_path == path):
                print("Skipping duplicate playlist load")
                return
            
            self._last_loaded_path = path
            self.playlist = data
            print(f"\nLoaded {len(self.playlist.channels)} channels")
            
            # Save settings
            self.settings.save_setting("last_playlist", path)
            self.settings.save_setting("last_playlist_is_url", str(is_url).lower())
            
            # Update UI
            self._update_ui_safely()
            
        else:
            self.window.show_notification(
                f"Failed to load playlist: {data}", 
                NotificationType.ERROR
            )

    def _on_playlist_error(self, error_info):
        """Handle playlist loading error."""
        error, _ = error_info
        self.window.show_notification(
            f"Error loading playlist: {str(error)}", 
            NotificationType.ERROR
        )

    def _update_ui_safely(self):
        """Update UI elements after playlist changes with progress logging."""
        try:
            print("\n=== Starting UI update ===")
            
            print("Updating categories...")
            self._update_categories()
            
            print("Updating channel list...")
            self._update_channel_list()
            
            print("=== UI update completed ===\n")
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
        # Temporarily disconnect category change signal if it exists
        try:
            self.window.category_combo.currentTextChanged.disconnect()
        except TypeError:
            pass  # Signal wasn't connected
        
        self.window.category_combo.clear()
        self.window.category_combo.addItem("All")
        self.window.category_combo.addItems(self.playlist.categories)
        
        # Reconnect the signal
        self.window.category_combo.currentTextChanged.connect(self.refresh_channels)

    def _update_channel_list(self):
        """Update channel list based on selected category."""
        if self._is_updating:
            print("Channel list update already in progress, skipping...")
            return
            
        self._is_updating = True
        try:
            category = self.window.category_combo.currentText()
            self.window.channel_list.clear()

            channels = (
                self.playlist.channels
                if category == Config.DEFAULT_CATEGORY
                else self.playlist.get_channels_by_category(category)
            )

            # Temporarily disable sorting and updates
            self.window.channel_list.setSortingEnabled(False)
            self.window.channel_list.setUpdatesEnabled(False)

            # Add all items at once
            channel_names = [channel.name for channel in channels]
            self.window.channel_list.addItems(channel_names)

            # Re-enable sorting and updates
            self.window.channel_list.setSortingEnabled(True)
            self.window.channel_list.setUpdatesEnabled(True)

            print(f"Added {len(channel_names)} channels to list")

        except Exception as e:
            print(f"Error updating channel list: {str(e)}")
            raise
        finally:
            self._is_updating = False

    def refresh_channels(self):
        """Update the channel list display based on current category and filters."""
        print("refresh_channels called")  # Debug
        self._update_channel_list()
