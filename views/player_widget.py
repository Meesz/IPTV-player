"""
This module contains the PlayerWidget class, 
which is responsible for displaying and controlling VLC media playback.
"""

import sys
import logging
import time
import threading

# pylint: disable=no-name-in-module
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget, QMessageBox
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from views.vlc_manager import VLCManager

# Configure logger
logger = logging.getLogger(__name__)


class MediaEventHandler(QObject):
    """Handler for VLC media events with Qt signals."""
    
    error_occurred = pyqtSignal(str)
    media_playing = pyqtSignal()
    media_stopped = pyqtSignal()
    media_buffering = pyqtSignal(float)
    
    def __init__(self, player):
        super().__init__()
        self.player = player
        self.vlc = VLCManager.get_vlc()
        self._setup_events()
        
    def _setup_events(self):
        """Set up event handlers for VLC media events."""
        if not self.player:
            return
            
        events = self.player.event_manager()
        events.event_attach(self.vlc.EventType.MediaPlayerPlaying, self._on_playing)
        events.event_attach(self.vlc.EventType.MediaPlayerStopped, self._on_stopped)
        events.event_attach(self.vlc.EventType.MediaPlayerEncounteredError, self._on_error)
        events.event_attach(self.vlc.EventType.MediaPlayerBuffering, self._on_buffering)
    
    def _on_playing(self, event):
        """Handle MediaPlayerPlaying event."""
        logger.info("Media playback started")
        self.media_playing.emit()
    
    def _on_stopped(self, event):
        """Handle MediaPlayerStopped event."""
        logger.info("Media playback stopped")
        self.media_stopped.emit()
    
    def _on_error(self, event):
        """Handle MediaPlayerEncounteredError event."""
        error_msg = "Media playback failed"
        logger.error(error_msg)
        self.error_occurred.emit(error_msg)
    
    def _on_buffering(self, event):
        """Handle MediaPlayerBuffering event."""
        cache_percentage = event.u.new_cache if hasattr(event, 'u') else 0
        self.media_buffering.emit(cache_percentage)


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

        # Create status overlay
        self.status_overlay = QLabel()
        self.status_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 128); color: white; font-weight: bold; padding: 10px; border-radius: 5px;")
        self.status_overlay.hide()
        self.layout.addWidget(self.status_overlay)

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
        
        # Create event handler
        self.event_handler = MediaEventHandler(self.player)
        self.event_handler.error_occurred.connect(self._handle_playback_error)
        self.event_handler.media_playing.connect(self._on_media_playing)
        self.event_handler.media_stopped.connect(self._on_media_stopped)
        self.event_handler.media_buffering.connect(self._on_media_buffering)
        
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
        
        # Track current media
        self.current_url = None
        self.fullscreen_window = None
        
        # Setup reconnection mechanism
        self.reconnect_timer = threading.Timer(0, lambda: None)
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5

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
            if hasattr(self, 'fullscreen_window') and self.fullscreen_window:
                self._exit_fullscreen()
            self.player.stop()
            self.player.release()
            self.instance.release()
            self.vlc_available = False
            
            # Cancel any pending reconnect
            self.reconnect_timer.cancel()

    def close_event(self, event):
        """Handle cleanup when widget is closed"""
        self.cleanup_vlc()
        super().close_event(event)
        
    def _show_status(self, message, duration=2000):
        """Show a temporary status message overlay."""
        self.status_overlay.setText(message)
        self.status_overlay.show()
        
        # Hide after duration
        def hide_status():
            self.status_overlay.hide()
            
        timer = threading.Timer(duration/1000, hide_status)
        timer.daemon = True
        timer.start()

    def play(self, url: str):
        """Play media from the given URL.

        Args:
            url: The URL of the media to play.
        """
        if not self.vlc_available:
            return
            
        # Cancel any pending reconnect
        self.reconnect_timer.cancel()
        self.reconnect_attempts = 0
        self.current_url = url

        try:
            logger.info(f"Attempting to play: {url}")
            self._show_status("Connecting to stream...")
            
            # Create media with optimized options
            media = self.instance.media_new(url)
            
            # Configure network caching based on protocol
            if url.startswith(("rtmp://", "rtsp://")):
                # Use larger cache for RTMP/RTSP
                media.add_option("network-caching=1500")
            elif url.startswith("http"):
                # Less cache for HTTP/HLS to reduce latency
                media.add_option("network-caching=1000")
            else:
                # Default cache
                media.add_option("network-caching=1000")
                
            # Add common options for better playback
            media.add_option("clock-jitter=0")
            media.add_option("clock-synchro=0")
            media.add_option("no-audio-time-stretch")
            
            # Add adaptive streaming options for HLS/DASH
            if url.endswith((".m3u8", ".mpd")):
                media.add_option(":adaptive-logic=highest")
                media.add_option(":adaptive-maxwidth=1920")
                media.add_option(":adaptive-maxheight=1080")

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

    def _on_media_playing(self):
        """Handle when media starts playing."""
        self.placeholder.hide()
        self.status_overlay.hide()
        self.reconnect_attempts = 0  # Reset reconnect counter on success

    def _on_media_stopped(self):
        """Handle when media is stopped."""
        self.placeholder.show()
        
    def _on_media_buffering(self, cache_percentage):
        """Handle buffering events."""
        if cache_percentage < 100:
            self._show_status(f"Buffering: {int(cache_percentage)}%")
        else:
            self.status_overlay.hide()

    def _handle_playback_error(self, error_msg):
        """Handle VLC playback errors with auto-reconnect"""
        self.placeholder.setText(error_msg)
        self.placeholder.show()
        
        # Try to reconnect if we have a current URL and haven't exceeded max attempts
        if self.current_url and self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            delay = min(2 ** self.reconnect_attempts, 30)  # Exponential backoff with max 30s
            
            reconnect_msg = f"Stream connection failed. Reconnecting in {delay}s... (Attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})"
            logger.warning(reconnect_msg)
            self._show_status(reconnect_msg, duration=delay*1000)
            
            # Schedule reconnect
            self.reconnect_timer.cancel()
            self.reconnect_timer = threading.Timer(delay, self._reconnect)
            self.reconnect_timer.daemon = True
            self.reconnect_timer.start()
        else:
            logger.error(f"Stream playback failed after {self.reconnect_attempts} attempts")
            self._show_status("Stream unavailable", duration=5000)
    
    def _reconnect(self):
        """Attempt to reconnect to the current stream."""
        if self.current_url:
            logger.info(f"Attempting to reconnect to: {self.current_url}")
            try:
                self.play(self.current_url)
            except Exception as e:
                logger.error(f"Reconnection failed: {str(e)}")

    def stop(self):
        """Stop media playback."""
        if self.vlc_available:
            if hasattr(self, 'fullscreen_window') and self.fullscreen_window:
                self._exit_fullscreen()
            self.player.stop()
            self.placeholder.show()
            
            # Cancel any pending reconnect
            self.reconnect_timer.cancel()
            self.reconnect_attempts = 0

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
