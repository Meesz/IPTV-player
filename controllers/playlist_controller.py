"""
This module contains the PlaylistController class, 
which is responsible for loading and displaying the playlist data.
"""

import os
import tempfile
import requests
from requests.exceptions import RequestException, Timeout
import logging
from PyQt6.QtCore import QObject, pyqtSignal
from models.playlist import Playlist
from utils.m3u_parser import M3UParser
from views.notification import NotificationType

# Configure logger
logger = logging.getLogger(__name__)

class PlaylistController(QObject):
    """Controller for managing playlists and updating the UI."""
    
    # Define signal for playlist loaded event
    playlist_loaded = pyqtSignal(Playlist)

    def __init__(self, main_window, settings_controller):
        super().__init__()
        self.window = main_window
        self.settings = settings_controller
        self.playlist = Playlist()

    def load_playlist_from_path(self, path: str, is_url: bool = False, max_retries: int = 3) -> bool:
        """Load a playlist from a file path or URL.
        
        Args:
            path: The file path or URL to load.
            is_url: True if path is a URL, False for local file path.
            max_retries: Maximum number of retry attempts for URL downloads.
            
        Returns:
            bool: True if loading succeeded, False otherwise.
        """
        tmp_path = None
        try:
            if is_url:
                # Download playlist from URL with retry logic
                logger.info(f"Downloading playlist from URL: {path}")
                
                for attempt in range(max_retries):
                    try:
                        logger.debug(f"Download attempt {attempt + 1}/{max_retries}")
                        response = requests.get(path, timeout=30)
                        response.raise_for_status()
                        break
                    except Timeout:
                        if attempt < max_retries - 1:
                            logger.warning(f"Timeout downloading playlist, retrying ({attempt + 1}/{max_retries})")
                            continue
                        else:
                            logger.error(f"Failed to download playlist after {max_retries} attempts")
                            raise TimeoutError(f"Timed out downloading playlist after {max_retries} attempts")
                    except RequestException as e:
                        logger.error(f"Request error: {str(e)}")
                        raise RuntimeError(f"Error downloading playlist: {str(e)}")

                # Save to temporary file
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".m3u8"
                ) as tmp_file:
                    tmp_file.write(response.content)
                    tmp_path = tmp_file.name
                    logger.debug(f"Downloaded playlist saved to: {tmp_path}")

                # Parse the temporary file
                logger.info("Parsing downloaded playlist")
                self.playlist = M3UParser.parse(tmp_path)
            else:
                # Parse local file
                logger.info(f"Loading playlist from local file: {path}")
                self.playlist = M3UParser.parse(path)

            # Save settings
            self.settings.save_setting("last_playlist", path)
            self.settings.save_setting("last_playlist_is_url", str(is_url).lower())

            logger.info(f"Loaded playlist with {len(self.playlist.channels)} channels")
            self._update_ui()
            
            # Emit the playlist_loaded signal
            logger.debug("Emitting playlist_loaded signal")
            self.playlist_loaded.emit(self.playlist)
            
            return True

        except FileNotFoundError as e:
            error_msg = f"Playlist file not found: {str(e)}"
            logger.error(error_msg)
            self.window.show_notification(error_msg, NotificationType.ERROR)
            return False
        except TimeoutError as e:
            error_msg = str(e)
            logger.error(error_msg)
            self.window.show_notification(error_msg, NotificationType.ERROR)
            return False
        except (ValueError, RuntimeError) as e:
            error_msg = f"Failed to load playlist: {str(e)}"
            logger.error(error_msg)
            self.window.show_notification(error_msg, NotificationType.ERROR)
            return False
        except Exception as e:
            error_msg = f"Unexpected error loading playlist: {str(e)}"
            logger.error(error_msg)
            self.window.show_notification(error_msg, NotificationType.ERROR)
            return False
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                    logger.debug(f"Temporary file removed: {tmp_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove temporary file: {str(e)}")

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
