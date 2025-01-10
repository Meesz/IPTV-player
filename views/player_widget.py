"""
This module contains the PlayerWidget class, 
which is responsible for displaying and controlling VLC media playback.
"""

import sys
import os
import logging

# pylint: disable=no-name-in-module
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMouseEvent
from .loading_spinner import LoadingSpinner
from views.vlc_manager import VLCManager


# Configure logger
logger = logging.getLogger(__name__)


class FullscreenWindow(QWidget):
    """A window that displays the player widget in fullscreen mode."""

    def __init__(self, player_widget):
        """Initialize the FullscreenWindow.

        Args:
            player_widget: The player widget to display in fullscreen.
        """
        super().__init__()
        self.player_widget = player_widget
        self.player = player_widget.player  # Get the VLC player instance

        # Make window resizable
        self.setWindowFlags(Qt.WindowType.Window)

        # Set black background
        self.setStyleSheet("background-color: black;")

        # Show window first
        self.showFullScreen()

        # Update VLC rendering target after window is shown
        self._update_vlc_rendering_target()

    def _update_vlc_rendering_target(self):
        """Update VLC rendering target based on platform"""
        if self.player_widget.vlc_available:
            if sys.platform == "win32":
                self.player.set_hwnd(self.winId())
            elif sys.platform.startswith("linux"):
                self.player.set_xwindow(self.winId())
            elif sys.platform == "darwin":
                self.player.set_nsobject(int(self.winId()))

    def resize_event(self, event):
        """Handle resize to update VLC rendering target"""
        super().resizeEvent(event)
        self._update_vlc_rendering_target()

    def mouse_double_click_event(self, event: QMouseEvent):
        """Handle double click to close the fullscreen window."""
        self.close()

    def key_press_event(self, event):
        """Handle key press events to close the fullscreen window on ESC key."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()


class PlayerWidget(QFrame):
    """A widget that displays and controls VLC media playback."""

    def __init__(self):
        """Initialize the PlayerWidget."""
        super().__init__()
        self.setMinimumSize(400, 300)

        # Create layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Create placeholder label
        self.placeholder = QLabel("No media playing")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.placeholder)

        # Initialize VLC
        success, error = VLCManager.initialize()
        self.vlc_available = success
        if not success:
            self.placeholder.setText(error)
            logger.error(error)
            return

        # Store VLC module and instance references
        self.vlc = VLCManager.get_vlc()
        self.instance = VLCManager.get_instance()

        # Create player
        self.player = VLCManager.create_player()
        self._setup_player()

        # Track fullscreen window
        self.fullscreen_window = None

        # Enable mouse tracking
        self.setMouseTracking(True)

        # Create loading spinner
        self.loading_spinner = LoadingSpinner(self)
        self.loading_spinner.hide()

        # Center the spinner
        self.loading_spinner.move(
            (self.width() - self.loading_spinner.width()) // 2,
            (self.height() - self.loading_spinner.height()) // 2,
        )

    def _setup_player(self):
        """Configure the VLC player instance."""
        if not self.vlc_available:
            return

        # Set up the window for VLC playback
        if sys.platform == "win32":
            self.player.set_hwnd(self.winId())
        elif sys.platform.startswith("linux"):
            self.player.set_xwindow(self.winId())
        elif sys.platform == "darwin":
            self.player.set_nsobject(int(self.winId()))

        # Set optimized media options

        self.player.video_set_key_input(False)
        self.player.video_set_mouse_input(False)

    def cleanup_vlc(self):
        """Clean up VLC resources before application shutdown"""
        if self.vlc_available:
            if self.fullscreen_window:
                self._exit_fullscreen()
            self.player.stop()
            self.player.release()
            self.instance.release()
            self.vlc_available = False

    def close_event(self, event):
        """Handle cleanup when widget is closed"""
        self.cleanup_vlc()
        super().close_event(event)

    def play(self, url: str):
        """Play media from the given URL.

        Args:
            url: The URL of the media to play.
        """
        if not self.vlc_available:
            return

        # Show loading spinner
        self.loading_spinner.start()
        self.placeholder.hide()

        try:
            # Create media with optimized options
            media = self.instance.media_new(url)
            media.add_option("network-caching=1000")
            media.add_option("clock-jitter=0")
            media.add_option("clock-synchro=0")
            media.add_option("no-audio-time-stretch")

            # Add event manager to detect when media starts playing
            events = self.player.event_manager()
            events.event_attach(
                self.vlc.EventType.MediaPlayerPlaying,
                lambda x: self.loading_spinner.stop(),
            )
            events.event_attach(
                self.vlc.EventType.MediaPlayerEncounteredError,
                lambda x: self._handle_playback_error(),
            )

            self.player.set_media(media)
            result = self.player.play()

            if result == -1:
                self.loading_spinner.stop()
                error_msg = "Failed to start playback - invalid or unsupported media"
                logger.error("Playback error: %s", error_msg)
                self.placeholder.setText(error_msg)
                self.placeholder.show()
                raise RuntimeError(error_msg)
        except Exception as e:
            self.loading_spinner.stop()
            error_msg = f"Playback error: {str(e)}"
            logger.error(error_msg)
            self.placeholder.setText(error_msg)
            self.placeholder.show()
            raise e

    def _handle_playback_error(self):
        """Handle VLC playback errors"""
        self.loading_spinner.stop()
        error_msg = "Stream playback failed - please check the URL and try again"
        logger.error(error_msg)
        self.placeholder.setText(error_msg)
        self.placeholder.show()

    def stop(self):
        """Stop media playback."""
        if self.vlc_available:
            if self.fullscreen_window:
                self._exit_fullscreen()
            self.player.stop()
            self.loading_spinner.stop()
            self.placeholder.show()

    def pause(self):
        """Pause media playback."""
        if self.vlc_available:
            self.player.pause()

    def set_volume(self, volume: int):
        """Set the audio volume level.

        Args:
            volume: Integer between 0 and 100 representing volume percentage
        """
        if not self.vlc_available:
            return

        # Clamp volume between 0 and 100
        volume = max(0, min(100, volume))
        self.player.audio_set_volume(volume)

    def is_paused(self) -> bool:
        """Check if the media is paused.

        Returns:
            bool: True if the media is paused, False otherwise.
        """
        if not self.vlc_available:
            return False
        try:
            return self.player.get_state() == self.vlc.State.Paused
        except AttributeError:
            logger.error("AttributeError: Failed to get player state")
            return False
        except TypeError:
            logger.error("TypeError: Failed to get player state")
            return False
        except (RuntimeError, ValueError) as e:
            logger.error("RuntimeError or ValueError: %s", str(e))
            return False
        except Exception as e:
            logger.error("Unexpected error: %s", str(e))
            return False

    def mouse_double_click_event(self):
        """Handle double click for fullscreen toggle.

        Args:
            event (QMouseEvent): The mouse event that triggered the double click.
        """
        if not self.vlc_available or not self.player.is_playing():
            return

        if self.fullscreen_window is None:
            self.fullscreen_window = FullscreenWindow(self)
            self.fullscreen_window.destroyed.connect(self._on_fullscreen_closed)
        else:
            self._exit_fullscreen()

    def _exit_fullscreen(self):
        """Exit fullscreen mode and restore video to the main window."""
        if self.fullscreen_window:
            # Restore video to main window
            if sys.platform == "win32":
                self.player.set_hwnd(self.winId())
            elif sys.platform.startswith("linux"):
                self.player.set_xwindow(self.winId())
            elif sys.platform == "darwin":
                self.player.set_nsobject(int(self.winId()))

            self.fullscreen_window.close()
            self.fullscreen_window = None

    def _on_fullscreen_closed(self):
        """Callback for when the fullscreen window is closed."""
        self._exit_fullscreen()

    def key_press_event(self, event):
        """Handle ESC key to exit fullscreen.

        Args:
            event: The key event that triggered the action.
        """
        if event.key() == Qt.Key.Key_Escape and self.fullscreen_window:
            self._exit_fullscreen()

    def resize_event(self, event):
        """Handle resize to keep spinner centered.

        Args:
            event: The resize event that triggered the action.
        """
        super().resizeEvent(event)
        # Center the spinner
        self.loading_spinner.move(
            (self.width() - self.loading_spinner.width()) // 2,
            (self.height() - self.loading_spinner.height()) // 2,
        )
    def _init_vlc(self):
        """Initialize VLC player and set up the environment."""
        # Get VLC instance from VLCManager
        vlc_instance = VLCManager.get_instance()
        if not vlc_instance:
            logger.error("VLC not initialized")
            error_msg = "Error: VLC not initialized\nPlease restart the application"
            self.placeholder.setText(error_msg)
            return

        # Create media player
        try:
            self.player = VLCManager.create_player()
            self.vlc_available = True
        except Exception as e:
            logger.error("Failed to create VLC player: %s", str(e))
            error_msg = f"Error: Failed to create VLC player\n{str(e)}"
            self.placeholder.setText(error_msg)
            return
