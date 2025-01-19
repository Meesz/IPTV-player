"""
This module contains the PlayerController class, which manages the player, playlists, EPG, and UI interactions.
It handles various events such as category changes, channel selections, and playback controls.
The PlayerController class interacts with the main window, database, and other utility classes to provide a seamless user experience.
"""

# pylint: disable=no-name-in-module
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMessageBox, QDialog

from models.playlist import Channel
from views.main_window import MainWindow
from views.notification import NotificationType
from views.playlist_manager import PlaylistManagerDialog
from controllers.playlist_controller import PlaylistController
from controllers.epg_controller import EPGController
from controllers.settings_controller import SettingsController
from config import Config


class PlayerController:
    """Controller class for managing the player, playlists, EPG, and UI interactions."""

    def __init__(self, main_window: MainWindow):
        """Initialize the PlayerController with the main window and set up necessary components."""
        self.window = main_window
        self.current_channel = None

        # Initialize sub-controllers
        self.settings = SettingsController()
        self.playlist_controller = PlaylistController(main_window, self.settings)
        self.epg_controller = EPGController(main_window, self.settings)

        # Create search timer for debouncing
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(Config.SEARCH_DEBOUNCE_DELAY)
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

    def _load_initial_state(self):
        """Load the initial application state."""
        # Load volume
        volume = int(self.settings.get_setting("volume", str(Config.DEFAULT_VOLUME)))
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
            self.epg_controller.load_epg_from_file(last_epg)

    def _category_changed(self, category: str):
        self.playlist_controller.refresh_channels()
        self.settings.save_setting("last_category", category)

    def _channel_selected(self, item):
        if not item:
            return

        selected_name = item.text()
        category = self.window.category_combo.currentText()
        channels = (
            self.playlist_controller.playlist.channels
            if category == "All"
            else self.playlist_controller.playlist.get_channels_by_category(category)
        )

        for channel in channels:
            if channel.name == selected_name:
                self.current_channel = channel
                print(f"Selected channel: {channel.name} - URL: {channel.url}")
                self._play_channel(channel)
                self.window.favorite_button.setChecked(
                    self.settings.db.is_favorite(channel.url)
                )
                break

    def _favorite_selected(self, item):
        favorites = self.settings.db.get_favorites()
        self.current_channel = favorites[self.window.favorites_list.row(item)]
        print(f"Selected favorite: {self.current_channel.name} - URL: {self.current_channel.url}")
        self._play_channel(self.current_channel)
        self.window.favorite_button.setChecked(True)

    def _play_channel(self, channel: Channel):
        try:
            print(f"Playing channel: {channel.name} - URL: {channel.url}")
            self.window.player_widget.play(channel.url)
            self.current_channel = channel
            self.epg_controller.refresh_epg()
            self.window.show_notification(
                f"Playing: {channel.name}", NotificationType.INFO
            )
        except Exception as e:
            self.window.show_notification(
                f"Failed to play channel: {str(e)}", NotificationType.ERROR
            )

    def _toggle_favorite(self, checked: bool):
        if not self.current_channel:
            return

        if checked:
            if self.settings.db.add_favorite(self.current_channel):
                self._load_favorites()
                self.window.show_notification(
                    f"Added {self.current_channel.name} to favorites",
                    NotificationType.SUCCESS,
                )
            else:
                self.window.favorite_button.setChecked(False)
                self.window.show_notification(
                    "Failed to add favorite", NotificationType.ERROR
                )
        elif self.settings.db.remove_favorite(self.current_channel.url):
            self._load_favorites()
            self.window.show_notification(
                f"Removed {self.current_channel.name} from favorites",
                NotificationType.SUCCESS,
            )
        else:
            self.window.favorite_button.setChecked(True)
            self.window.show_notification(
                "Failed to remove favorite", NotificationType.ERROR
            )

    def _load_favorites(self):
        self.window.favorites_list.clear()
        for channel in self.settings.db.get_favorites():
            self.window.favorites_list.addItem(channel.name)

    def _perform_search(self):
        """Perform the search operation and update the channel list based on the search text."""
        search_text = self.window.search_bar.text().lower()

        if not search_text:
            self.playlist_controller.refresh_channels()
            return

        # Get channels based on category
        category = self.window.category_combo.currentText()
        if category == "All":
            channels = self.playlist_controller.playlist.channels
        else:
            channels = self.playlist_controller.playlist.get_channels_by_category(
                category
            )

        # Filter channels
        matched_channels = [
            channel for channel in channels if search_text in channel.name.lower()
        ]

        # Update list
        self.window.channel_list.clear()
        for channel in matched_channels:
            self.window.channel_list.addItem(channel.name)

    def toggle_playback(self):
        """Toggle playback between play and pause states."""
        if self.window.player_widget.vlc_available:
            self.window.player_widget.pause()
            status = "Paused" if self.window.player_widget.is_paused() else "Playing"
            self.window.show_notification(status, NotificationType.INFO)

    def stop_playback(self):
        """Stop the playback."""
        if self.window.player_widget.vlc_available:
            self.window.player_widget.stop()
            self.window.show_notification("Playback stopped", NotificationType.INFO)

    def volume_changed(self, value: int):
        """Handle volume change event and update the volume setting.

        Args:
            value (int): The new volume value.
        """
        self.window.player_widget.set_volume(value)
        self.settings.save_setting("volume", str(value))
        if value == 0:
            self.window.show_notification("Muted", NotificationType.INFO)
        elif value == 100:
            self.window.show_notification("Maximum volume", NotificationType.INFO)

    @property
    def playlist(self):
        """Get the playlist from the playlist controller.

        Returns:
            Playlist: The current playlist
        """
        return self.playlist_controller.playlist

    def show_playlist_manager(self, retry_count=0, max_retries=3):
        """Show the playlist manager dialog and handle playlist management.

        Args:
            retry_count (int): The current retry count for loading a playlist.
            max_retries (int): The maximum number of retries allowed.
        """
        try:
            dialog = PlaylistManagerDialog(self.window)

            # Load saved playlists
            saved_playlists = self.settings.db.get_playlists()
            dialog.set_playlists(saved_playlists)

            # Connect playlist selected signal
            dialog.playlist_selected.connect(
                self.playlist_controller.load_playlist_from_path
            )

            result = dialog.exec()

            # Always save playlists when dialog is closed
            playlists = dialog.get_playlists()
            if playlists:
                success = self.settings.db.save_playlists(playlists)
                if success:
                    self.window.show_notification(
                        f"Saved {len(playlists)} playlists successfully",
                        NotificationType.SUCCESS,
                    )
                else:
                    self.window.show_notification(
                        "Failed to save playlists", NotificationType.ERROR
                    )

            # Only show quit confirmation if we have no channels at all
            if result == QDialog.DialogCode.Rejected and not self.playlist.channels:
                if retry_count >= max_retries:
                    self.window.show_notification(
                        "No playlist loaded after multiple attempts. Closing application.",
                        NotificationType.WARNING,
                    )
                    self.window.close()
                    return

                response = QMessageBox.question(
                    self.window,
                    "No Playlist",
                    "No playlist is loaded. Would you like to add one?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )

                if response == QMessageBox.StandardButton.Yes:
                    QTimer.singleShot(
                        0,
                        lambda: self.show_playlist_manager(
                            retry_count + 1, max_retries
                        ),
                    )
                else:
                    self.window.close()

        except Exception as e:
            self.window.show_notification(
                f"Error showing playlist manager: {str(e)}", NotificationType.ERROR
            )
