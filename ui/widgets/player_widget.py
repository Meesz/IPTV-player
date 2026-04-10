import sys
import logging
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from infra.playback.vlc_backend import VLCBackend

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
        self.vlc = VLCBackend.get_vlc()
        self._setup_events()
        
    def _setup_events(self):
        if not self.player:
            return
            
        events = self.player.event_manager()
        events.event_attach(self.vlc.EventType.MediaPlayerPlaying, self._on_playing)
        events.event_attach(self.vlc.EventType.MediaPlayerStopped, self._on_stopped)
        events.event_attach(self.vlc.EventType.MediaPlayerEncounteredError, self._on_error)
        events.event_attach(self.vlc.EventType.MediaPlayerBuffering, self._on_buffering)
    
    def _on_playing(self, event):
        self.media_playing.emit()
    
    def _on_stopped(self, event):
        self.media_stopped.emit()
    
    def _on_error(self, event):
        self.error_occurred.emit("Media playback failed")
    
    def _on_buffering(self, event):
        cache_percentage = event.u.new_cache if hasattr(event, "u") else 0
        self.media_buffering.emit(cache_percentage)

class PlayerWidget(QFrame):
    """A widget that displays and controls VLC media playback."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(400, 300)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.placeholder = QLabel("No media playing")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.placeholder)

        self.status_overlay = QLabel()
        self.status_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 128); color: white; font-weight: bold; padding: 10px; border-radius: 5px;")
        self.status_overlay.hide()
        self.layout.addWidget(self.status_overlay)

        success, error = VLCBackend.initialize()
        self.vlc_available = success
        self.vlc = None
        self.instance = None
        self.player = None
        if not success:
            self.placeholder.setText(error)
            return

        self.vlc = VLCBackend.get_vlc()
        self.instance = VLCBackend.get_instance()
        self.player = VLCBackend.create_player()
        
        self.event_handler = MediaEventHandler(self.player)
        self.event_handler.error_occurred.connect(self._handle_playback_error)
        self.event_handler.media_playing.connect(self._on_media_playing)
        self.event_handler.media_stopped.connect(self._on_media_stopped)
        self.event_handler.media_buffering.connect(self._on_media_buffering)
        
        self._setup_player()

        self.setMouseTracking(True)
        self.is_fullscreen = False
        self.current_url = None
        self.normal_geometry = None
        self.normal_parent = None
        self.normal_layout = None
        self.normal_index = None
        self.normal_stretch = None
        
        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.setSingleShot(True)
        self.reconnect_timer.timeout.connect(self._reconnect)
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5

    def _setup_player(self):
        if not self.vlc_available or not self.player:
            return

        try:
            if sys.platform == "win32":
                self.player.set_hwnd(self.winId())
            elif sys.platform.startswith("linux"):
                window_id = int(self.winId())
                self.player.set_xwindow(window_id)
            elif sys.platform == "darwin":
                self.player.set_nsobject(int(self.winId()))
            self.player.video_set_key_input(False)
            self.player.video_set_mouse_input(False)
        except Exception as exc:
            logger.warning("Failed to bind VLC window handle: %s", exc)

    def play(self, url: str):
        if not self.vlc_available or not self.player:
            self.placeholder.setText("VLC backend unavailable")
            self.placeholder.show()
            return
            
        self.reconnect_timer.stop()
        self.reconnect_attempts = 0
        self.current_url = url

        try:
            self._show_status("Connecting to stream...")
            media = self.instance.media_new(url)
            
            if url.startswith(("rtmp://", "rtsp://")):
                media.add_option("network-caching=1500")
            else:
                media.add_option("network-caching=1000")
                
            media.add_option("clock-jitter=0")
            media.add_option("clock-synchro=0")
            
            self.player.set_media(media)
            self.player.play()
        except Exception as e:
            self._handle_playback_error(str(e))

    def stop(self):
        if self.vlc_available and self.player:
            if self.is_fullscreen:
                self._exit_fullscreen()
            self.player.stop()
            self.placeholder.show()
            self.reconnect_timer.stop()

    def pause(self):
        if self.vlc_available and self.player:
            self.player.pause()

    def set_volume(self, volume: int):
        if self.vlc_available and self.player:
            self.player.audio_set_volume(max(0, min(100, volume)))

    def _show_status(self, message, duration=2000):
        self.status_overlay.setText(message)
        self.status_overlay.show()
        QTimer.singleShot(duration, self.status_overlay.hide)

    def _on_media_playing(self):
        self.placeholder.hide()
        self.status_overlay.hide()
        self.reconnect_attempts = 0

    def _on_media_stopped(self):
        self.placeholder.show()

    def _on_media_buffering(self, cache_percentage):
        if cache_percentage < 100:
            self._show_status(f"Buffering: {int(cache_percentage)}%")
        else:
            self.status_overlay.hide()

    def _handle_playback_error(self, error_msg):
        self.placeholder.setText(error_msg)
        self.placeholder.show()
        
        if self.current_url and self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            delay = min(2 ** self.reconnect_attempts, 30)
            self._show_status(f"Reconnecting in {delay}s...", duration=delay*1000)
            self.reconnect_timer.start(int(delay * 1000))

    def _reconnect(self):
        if self.current_url and self.player:
            self.play(self.current_url)

    def mouseDoubleClickEvent(self, event):
        if not self.vlc_available or not self.player or not self.player.is_playing():
            return

        if not self.is_fullscreen:
            self._enter_fullscreen()
        else:
            self._exit_fullscreen()

    def _enter_fullscreen(self):
        self.normal_geometry = self.geometry()
        self.normal_parent = self.parent()
        self.normal_layout = self.parent().layout() if self.parent() else None
        if self.normal_layout:
            self.normal_index = self.normal_layout.indexOf(self)
            self.normal_stretch = self.normal_layout.stretch(self.normal_index)
            self.normal_layout.removeWidget(self)

        for widget in self.window().findChildren(QWidget):
            if widget is not self and widget.isVisible():
                widget.hide()
                widget.setProperty("was_visible", True)

        self.window().setWindowState(Qt.WindowState.WindowFullScreen)
        self.setParent(self.window())
        self.setGeometry(self.window().rect())
        self.raise_()
        self.show()
        self.is_fullscreen = True

    def _exit_fullscreen(self):
        if not self.parent():
            return
        self.window().setWindowState(Qt.WindowState.WindowNoState)
        self.setParent(self.normal_parent)
        if self.normal_layout and self.normal_index is not None:
            self.normal_layout.insertWidget(self.normal_index, self, stretch=self.normal_stretch)
        self.setGeometry(self.normal_geometry)

        for widget in self.window().findChildren(QWidget):
            if widget is not self and widget.property("was_visible"):
                widget.show()
                widget.setProperty("was_visible", False)

        self.is_fullscreen = False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.is_fullscreen:
            self._exit_fullscreen()
