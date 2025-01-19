"""
This module contains the PlayerWidget class, 
which is responsible for displaying and controlling VLC media playback.
"""

import sys
import logging

# pylint: disable=no-name-in-module
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt
from views.vlc_manager import VLCManager

# Configure logger
logger = logging.getLogger(__name__)


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

        # Enable mouse tracking
        self.setMouseTracking(True)

        # Track fullscreen state
        self.is_fullscreen = False
        self.normal_geometry = None
        self.normal_parent = None
        self.normal_layout = None
        self.normal_index = None
        self.normal_stretch = None

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
                lambda x: self.placeholder.hide(),  # Hide placeholder when playing starts
            )
            events.event_attach(
                self.vlc.EventType.MediaPlayerEncounteredError,
                lambda x: self._handle_playback_error(),
            )

            self.player.set_media(media)
            result = self.player.play()

            if result == -1:
                error_msg = "Failed to start playback - invalid or unsupported media"
                logger.error("Playback error: %s", error_msg)
                self.placeholder.setText(error_msg)
                self.placeholder.show()
                raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Playback error: {str(e)}"
            logger.error(error_msg)
            self.placeholder.setText(error_msg)
            self.placeholder.show()
            raise e

    def _handle_playback_error(self):
        """Handle VLC playback errors"""
        error_msg = "Stream playback failed - please check the URL and try again"
        logger.error(error_msg)
        self.placeholder.setText(error_msg)
        self.placeholder.show()

    def stop(self):
        """Stop media playback."""
        if self.vlc_available:
            if self.is_fullscreen:
                self._exit_fullscreen()
            self.player.stop()
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

    def mouseDoubleClickEvent(self, event):
        """Handle double click for fullscreen toggle."""
        print("PlayerWidget: Double click detected")  # Debug
        if not self.vlc_available or not self.player.is_playing():
            print(
                "PlayerWidget: Double click - player not available or not playing"
            )  # Debug
            return

        if not self.is_fullscreen:
            print("PlayerWidget: Entering fullscreen")  # Debug
            # Store current geometry and parent
            self.normal_geometry = self.geometry()
            self.normal_parent = self.parent()
            self.normal_layout = self.parent().layout()
            self.normal_index = self.normal_layout.indexOf(self)
            self.normal_stretch = self.normal_layout.stretch(self.normal_index)

            # Remove from layout but keep parent
            self.normal_layout.removeWidget(self)

            # Hide other UI elements
            for widget in self.window().findChildren(QWidget):
                if widget is not self and widget.isVisible():
                    widget.hide()
                    widget.setProperty("was_visible", True)

            # Make window fullscreen
            self.window().setWindowState(Qt.WindowState.WindowFullScreen)

            # Reparent to main window and resize to fill it
            self.setParent(self.window())
            self.setGeometry(self.window().rect())
            self.raise_()  # Bring to front
            self.show()

            self.is_fullscreen = True
        else:
            print("PlayerWidget: Exiting fullscreen")  # Debug
            self._exit_fullscreen()

    def _exit_fullscreen(self):
        """Exit fullscreen mode."""
        if self.is_fullscreen:
            print("PlayerWidget: Restoring window state")  # Debug

            # Restore window state
            self.window().setWindowState(Qt.WindowState.WindowNoState)

            # Restore widget to original parent and layout
            self.setParent(self.normal_parent)
            self.normal_layout.insertWidget(
                self.normal_index, self, stretch=self.normal_stretch
            )
            self.setGeometry(self.normal_geometry)

            # Show previously visible widgets
            for widget in self.window().findChildren(QWidget):
                if widget is not self and widget.property("was_visible"):
                    widget.show()
                    widget.setProperty("was_visible", False)

            self.is_fullscreen = False

    def keyPressEvent(self, event):
        """Handle ESC key to exit fullscreen."""
        if event.key() == Qt.Key.Key_Escape and self.is_fullscreen:
            self._exit_fullscreen()

    def resizeEvent(self, event):
        """Handle resize events.

        Args:
            event: The resize event that triggered the action.
        """
        super().resizeEvent(event)

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
