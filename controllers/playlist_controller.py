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

    def load_playlist_from_path(self, path: str, is_url: bool = False) -> bool:
        """Load a playlist from the given path."""
        try:
            # Clear current playlist data
            self.playlist = None  # Clear existing playlist
            self.window.left_panel.channel_list.clear()
            self.window.left_panel.category_combo.clear()
            
            # Create new playlist instance and load channels
            self.playlist = Playlist.from_path(path, is_url)
            
            # Update UI
            self._update_categories()
            self._update_channel_list()
            
            # Save as last playlist
            self.settings.save_setting("last_playlist", path)
            self.settings.save_setting("last_playlist_is_url", str(is_url).lower())
            
            # Notify player controller
            if hasattr(self, 'player_controller') and self.player_controller:
                self.player_controller.on_playlist_changed()
            
            return True
            
        except Exception as e:
            self.window.show_notification(
                f"Failed to load playlist: {str(e)}", NotificationType.ERROR
            )
            return False

    def _load_playlist_worker(self, path: str, is_url: bool) -> tuple:
        """Worker function to load playlist in background."""
        tmp_path = None
        try:
            if is_url:
                print("\n=== Starting playlist download ===")
                print(f"URL: {path}")
                
                # Download content
                print("Sending HTTP request...")
                response = requests.get(path, timeout=Config.REQUEST_TIMEOUT)
                response.raise_for_status()
                
                # Log response details
                print(f"Response status: {response.status_code}")
                print(f"Response encoding: {response.encoding}")
                print(f"Content length: {len(response.content)} bytes")
                print(f"Content type: {response.headers.get('content-type', 'unknown')}")
                
                # Get content and detect encoding
                content = response.content
                
                # Try to detect encoding
                print("\nTesting content decoding:")
                detected_encoding = None
                for encoding in ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']:
                    try:
                        decoded = content.decode(encoding)
                        print(f"Successfully decoded with {encoding}")
                        detected_encoding = encoding
                        # Print first few characters to verify content
                        print(f"First 100 chars: {decoded[:100]}")
                        break
                    except UnicodeDecodeError as e:
                        print(f"Failed to decode with {encoding}: {e}")
                
                if not detected_encoding:
                    raise ValueError("Could not decode content with any supported encoding")
                
                # Create temporary file
                print("\nCreating temporary file...")
                with tempfile.NamedTemporaryFile(
                    mode='wb', delete=False, suffix=".m3u8"
                ) as tmp_file:
                    tmp_file.write(content)
                    tmp_path = tmp_file.name
                    print(f"Wrote content to: {tmp_path}")

                print("\nParsing playlist...")
                try:
                    playlist = M3UParser.parse(tmp_path)
                    print(f"Successfully parsed playlist with {len(playlist)} channels")
                    return (True, playlist, path, is_url)
                except Exception as parse_error:
                    print(f"\nError parsing playlist: {parse_error}")
                    # Try to read and print part of the file content
                    try:
                        with open(tmp_path, 'rb') as f:
                            sample = f.read(200)
                            print(f"\nFirst 200 bytes of file:\n{sample}")
                            print(f"\nAs hex:\n{sample.hex()}")
                    except Exception as read_error:
                        print(f"Error reading temp file: {read_error}")
                    raise parse_error

            else:
                print("Parsing local playlist file...")
                playlist = M3UParser.parse(path)
                return (True, playlist, path, is_url)

        except Exception as e:
            print(f"\n=== Error in playlist worker ===")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            return (False, str(e), None, None)

        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                    print(f"Cleaned up temporary file: {tmp_path}")
                except Exception as e:
                    print(f"Failed to cleanup temporary file: {e}")

    def _on_playlist_loaded(self, result):
        """Handle successful playlist loading."""
        success, data, path, is_url = result

        if success:
            # Check if this is a duplicate load
            if hasattr(self, "_last_loaded_path") and self._last_loaded_path == path:
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
                f"Failed to load playlist: {data}", NotificationType.ERROR
            )

    def _on_playlist_error(self, error_info):
        """Handle playlist loading error."""
        error, _ = error_info
        self.window.show_notification(
            f"Error loading playlist: {str(error)}", NotificationType.ERROR
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
                NotificationType.SUCCESS,
            )
        except Exception as e:
            print(f"Error during UI update: {str(e)}")
            self.window.show_notification(
                f"Error updating UI: {str(e)}", NotificationType.ERROR
            )

    def _update_categories(self):
        """Update the category combo box with available categories."""
        if not self.playlist:
            return

        self.window.left_panel.category_combo.clear()
        
        # Add "All" category first
        self.window.left_panel.category_combo.addItem(Config.DEFAULT_CATEGORY)
        
        # Add other categories
        categories = self.playlist.categories
        if categories:
            self.window.left_panel.category_combo.addItems(categories)

    def _update_channel_list(self):
        """Update the channel list with current category's channels."""
        if not self.playlist:
            return

        try:
            category = self.window.left_panel.category_combo.currentText()
            self.window.left_panel.channel_list.clear()

            # Get channels for current category
            channels = (
                self.playlist.channels
                if category == Config.DEFAULT_CATEGORY
                else self.playlist.get_channels_by_category(category)
            )

            # Add channels to list
            for channel in channels:
                self.window.left_panel.channel_list.addItem(channel.name)

        except Exception as e:
            print(f"Error updating channel list: {str(e)}")

    def refresh_channels(self, search_text: str = ""):
        """Update the channel list display."""
        if not hasattr(self, 'playlist') or not self.playlist:
            return
        
        try:
            category = self.window.left_panel.category_combo.currentText()
            channels = (
                self.playlist.channels
                if category == Config.DEFAULT_CATEGORY
                else self.playlist.get_channels_by_category(category)
            )

            if search_text:
                search_text = search_text.lower()
                channels = [
                    channel for channel in channels 
                    if search_text in channel.name.lower()
                ]

            self.window.left_panel.channel_list.clear()
            self.window.left_panel.channel_list.addItems([channel.name for channel in channels])
            
        except Exception as e:
            print(f"Error refreshing channels: {str(e)}")
