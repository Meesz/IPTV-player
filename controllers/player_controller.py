"""
This module contains the PlayerController class, which manages the player, playlists, EPG, and UI interactions.
It handles various events such as category changes, channel selections, and playback controls.
The PlayerController class interacts with the main window, database, and other utility classes to provide a seamless user experience.
"""

# pylint: disable=no-name-in-module
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMessageBox, QDialog
import logging
from typing import Optional

from models.playlist import Channel, Playlist
from views.main_window import MainWindow
from views.notification import NotificationType
from views.playlist_manager import PlaylistManagerDialog
from controllers.playlist_controller import PlaylistController
from controllers.epg_controller import EPGController
from controllers.settings_controller import SettingsController

logger = logging.getLogger(__name__)


class PlayerController:
    """Controller class for managing the player, playlists, EPG, and UI interactions."""

    def __init__(
        self,
        main_window: MainWindow,
        settings: SettingsController,
        playlist_controller: PlaylistController,
        epg_controller: EPGController
    ):
        """Initialize the PlayerController with dependencies.
        
        Args:
            main_window: The main window instance
            settings: The settings controller
            playlist_controller: The playlist controller
            epg_controller: The EPG controller
        """
        self.window = main_window
        self.settings = settings
        self.playlist_controller = playlist_controller
        self.epg_controller = epg_controller
        self.current_channel: Optional[Channel] = None

        # Create search timer for debouncing
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)
        self.search_timer.timeout.connect(self._perform_search)

        # Connect signals
        self._connect_signals()

        # Load initial state
        self._load_initial_state()

    def _connect_signals(self):
        """Connect UI signals to their respective handlers."""
        # Playlist and channels
        self.window.category_combo.currentTextChanged.connect(self._category_changed)
        self.window.channel_list.itemClicked.connect(self._channel_selected)
        self.window.favorites_list.itemClicked.connect(self._favorite_selected)

        # Playback controls
        self.window.play_button.clicked.connect(self.toggle_playback)
        self.window.stop_button.clicked.connect(self.stop_playback)
        self.window.volume_slider.valueChanged.connect(self.volume_changed)
        self.window.favorite_button.clicked.connect(self._toggle_favorite)

        # Search
        self.window.search_bar.textChanged.connect(self.search_timer.start)

        # Menu actions
        self.window.playlist_manager_action.triggered.connect(
            self.show_playlist_manager
        )
        
        # Connect to playlist loaded signal to map channels to EPG
        if hasattr(self.playlist_controller, 'playlist_loaded'):
            logger.debug("Connecting to playlist_loaded signal")
            self.playlist_controller.playlist_loaded.connect(self._on_playlist_loaded)

    def _load_initial_state(self):
        """Load the initial application state."""
        # Load volume
        volume = int(self.settings.get_setting("volume", "100"))
        self.window.volume_slider.setValue(volume)
        self.window.player_widget.set_volume(volume)

        # Load last playlist
        last_playlist = self.settings.get_setting("last_playlist")
        is_url = self.settings.get_setting("last_playlist_is_url") == "true"

        if last_playlist:
            self.playlist_controller.load_playlist_from_path(last_playlist, is_url)

        # Load last EPG
        last_epg = self.settings.get_setting("last_epg")
        if last_epg:
            self.epg_controller.load_epg(last_epg)
            
            # Auto-map channels to EPG if both are loaded
            if self.playlist_controller.playlist and self.playlist_controller.playlist.channels:
                self._map_channels_to_epg(self.playlist_controller.playlist)

    def _on_playlist_loaded(self, playlist: Playlist):
        """Handle playlist loaded event."""
        self._map_channels_to_epg(playlist)
        self._update_epg_display()

    def _map_channels_to_epg(self, playlist: Playlist):
        """Map channels to EPG data."""
        if not playlist or not playlist.channels:
            return
            
        for channel in playlist.channels:
            self.epg_controller.map_channel(channel)

    def _category_changed(self, category: str):
        """Handle category change event."""
        self.playlist_controller.filter_by_category(category)
        self._update_epg_display()

    def _channel_selected(self, item):
        """Handle channel selection event."""
        channel = item.data(0)
        self._play_channel(channel)

    def _favorite_selected(self, item):
        """Handle favorite selection event."""
        channel = item.data(0)
        self._play_channel(channel)

    def _play_channel(self, channel: Channel):
        """Play the selected channel."""
        if not channel or not channel.url:
            return
            
        self.current_channel = channel
        self.window.player_widget.play(channel.url)
        self._update_epg_display()

    def _update_epg_display(self):
        """Update the EPG display."""
        if not self.current_channel:
            return
            
        epg_data = self.epg_controller.get_channel_epg(self.current_channel)
        if epg_data:
            self.window.epg_widget.update_epg(epg_data)

    def _toggle_favorite(self, checked: bool):
        """Toggle favorite status for current channel."""
        if not self.current_channel:
            return
            
        self.playlist_controller.toggle_favorite(self.current_channel, checked)
        self._load_favorites()

    def _load_favorites(self):
        """Load favorite channels."""
        self.playlist_controller.load_favorites()

    def _perform_search(self):
        """Perform search with debouncing."""
        search_text = self.window.search_bar.text()
        self.playlist_controller.search_channels(search_text)

    def toggle_playback(self):
        """Toggle playback state."""
        self.window.player_widget.toggle_playback()

    def stop_playback(self):
        """Stop playback."""
        self.window.player_widget.stop()

    def volume_changed(self, value: int):
        """Handle volume change event."""
        self.window.player_widget.set_volume(value)
        self.settings.set_setting("volume", str(value))

    @property
    def playlist(self) -> Playlist:
        """Get the current playlist."""
        return self.playlist_controller.playlist

    def show_playlist_manager(self):
        """Show the playlist manager dialog."""
        dialog = PlaylistManagerDialog(self.window, self.playlist_controller)
        dialog.playlist_selected.connect(self._on_playlist_selected)
        dialog.exec()

    def _on_playlist_selected(self, path: str, is_url: bool):
        """Handle playlist selection from the playlist manager.
        
        Args:
            path: The path or URL of the selected playlist
            is_url: Whether the path is a URL
        """
        try:
            self.playlist_controller.load_playlist_from_path(path, is_url)
            # Save the last used playlist
            self.settings.set_setting("last_playlist", path)
            self.settings.set_setting("last_playlist_is_url", str(is_url).lower())
        except Exception as e:
            logger.error(f"Failed to load selected playlist: {str(e)}")
            QMessageBox.critical(
                self.window,
                "Error",
                f"Failed to load playlist: {str(e)}"
            )
