import sys
import os
import logging
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget, QHBoxLayout, QSlider
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QMouseEvent
from .loading_spinner import LoadingSpinner

# Configure logger
logger = logging.getLogger(__name__)

class FullscreenWindow(QWidget):
    def __init__(self, player_widget):
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
            elif sys.platform.startswith('linux'):
                self.player.set_xwindow(self.winId())
            elif sys.platform == "darwin":
                self.player.set_nsobject(int(self.winId()))
    
    def resizeEvent(self, event):
        """Handle resize to update VLC rendering target"""
        super().resizeEvent(event)
        self._update_vlc_rendering_target()
    
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        self.close()
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

class PlayerWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(400, 300)
        
        # Create main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Create video container widget
        self.video_container = QWidget()
        self.video_container.setStyleSheet("background-color: black;")
        
        # Create video layout to properly position the placeholder
        video_layout = QVBoxLayout(self.video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create placeholder label
        self.placeholder = QLabel("No media playing")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet("color: #ffffff;")
        video_layout.addWidget(self.placeholder)
        
        # Add video container to main layout with stretch
        self.layout.addWidget(self.video_container, 1)
        
        # Create controls container
        controls_container = QWidget()
        controls_container.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                min-height: 40px;
            }
        """)
        
        # Create seek bar layout
        seek_layout = QHBoxLayout(controls_container)
        seek_layout.setContentsMargins(10, 5, 10, 5)
        seek_layout.setSpacing(10)
        
        # Add current time label
        self.current_time_label = QLabel("00:00:00")
        self.current_time_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                background-color: transparent;
                min-width: 70px;
            }
        """)
        seek_layout.addWidget(self.current_time_label)
        
        # Add seek bar
        self.seek_bar = QSlider(Qt.Orientation.Horizontal)
        self.seek_bar.setEnabled(False)
        self.seek_bar.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 8px;
                background: #4d4d4d;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 1px solid #999999;
                width: 16px;
                margin: -4px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #f0f0f0;
            }
        """)
        seek_layout.addWidget(self.seek_bar)
        
        # Add duration label
        self.duration_label = QLabel("00:00:00")
        self.duration_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                background-color: transparent;
                min-width: 70px;
            }
        """)
        seek_layout.addWidget(self.duration_label)
        
        # Add controls container to main layout
        self.layout.addWidget(controls_container)
        
        # Initialize VLC
        self.vlc_available = False
        self._init_vlc()
        
        # Create timer for updating seek bar
        self.update_timer = QTimer()
        self.update_timer.setInterval(1000)  # Update every second
        self.update_timer.timeout.connect(self._update_seek_bar)
        
        # Connect seek bar signals
        self.seek_bar.sliderPressed.connect(self._seek_bar_pressed)
        self.seek_bar.sliderReleased.connect(self._seek_bar_released)
        
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
            (self.height() - self.loading_spinner.height()) // 2
        )
    
    def _init_vlc(self):
        try:
            # Try to determine Python architecture
            is_64bits = sys.maxsize > 2**32
            
            if sys.platform == "win32":
                vlc_path = "C:\\Program Files\\VideoLAN\\VLC" if is_64bits else "C:\\Program Files (x86)\\VideoLAN\\VLC"
                if not os.path.exists(vlc_path):
                    error_msg = (
                        f"Error: VLC not found in {vlc_path}\n"
                        f"Please install {'64' if is_64bits else '32'}-bit VLC"
                    )
                    self.placeholder.setText(error_msg)
                    logger.error(error_msg)
                    return
                
                os.environ['PATH'] = vlc_path + ';' + os.environ['PATH']
                os.add_dll_directory(vlc_path)
            
            # Import VLC with optimized parameters
            import vlc
            self.vlc = vlc  # Store vlc module as instance variable
            
            # Create VLC instance with optimized parameters
            self.instance = vlc.Instance(
                '--no-video-title-show',  # Don't show video title
                '--no-snapshot-preview',   # Disable snapshot preview
                '--quiet',                 # Reduce logging
                '--no-xlib',              # Optimize for modern systems
                '--network-caching=1000',  # 1 second network cache
                '--live-caching=300',      # 300ms live stream cache
                '--sout-mux-caching=300',  # 300ms mux cache
                '--embedded-video',        # Enable embedded video
                '--qt-minimal-view'        # Use minimal interface
            )
            
            self.player = self.instance.media_player_new()
            
            # Set up event manager for media player
            self.event_manager = self.player.event_manager()
            self.event_manager.event_attach(
                self.vlc.EventType.MediaPlayerTimeChanged,
                self._on_time_changed
            )
            self.event_manager.event_attach(
                self.vlc.EventType.MediaPlayerLengthChanged,
                self._on_length_changed
            )
            
            # Enable VLC's built-in controls
            if sys.platform == "win32":
                self.player.set_hwnd(self.video_container.winId())
            elif sys.platform.startswith('linux'):
                self.player.set_xwindow(self.video_container.winId())
            elif sys.platform == "darwin":
                self.player.set_nsobject(int(self.video_container.winId()))
            
            # Enable native controls
            self.player.video_set_mouse_input(True)
            self.player.video_set_key_input(True)
            
            self.vlc_available = True
            logger.info("VLC initialized successfully")
            
        except Exception as e:
            error_msg = (
                f"Error initializing VLC: {str(e)}\n"
                f"Python is {'64' if is_64bits else '32'}-bit\n"
                "Make sure you have the correct VLC version installed"
            )
            logger.error(error_msg)
            self.placeholder.setText(error_msg)
            self.vlc_available = False
    
    def cleanup_vlc(self):
        """Clean up VLC resources before application shutdown"""
        if self.vlc_available:
            if self.fullscreen_window:
                self._exit_fullscreen()
            self.player.stop()
            self.player.release()
            self.instance.release()
            self.vlc_available = False
    
    def closeEvent(self, event):
        """Handle cleanup when widget is closed"""
        self.cleanup_vlc()
        super().closeEvent(event)
    
    def play(self, url: str):
        if not self.vlc_available:
            return
        
        # Show loading spinner
        self.loading_spinner.start()
        self.placeholder.hide()
        
        try:
            # Create media with optimized options
            media = self.instance.media_new(url)
            media.add_option('network-caching=1000')
            media.add_option('clock-jitter=0')
            media.add_option('clock-synchro=0')
            media.add_option('no-audio-time-stretch')
            
            # Add event manager to detect when media starts playing
            events = self.player.event_manager()
            events.event_attach(
                self.vlc.EventType.MediaPlayerPlaying,
                lambda x: self._on_playing()
            )
            events.event_attach(
                self.vlc.EventType.MediaPlayerEncounteredError,
                lambda x: self._handle_playback_error()
            )
            
            self.player.set_media(media)
            result = self.player.play()
            
            if result == -1:
                self.loading_spinner.stop()
                error_msg = "Failed to start playback - invalid or unsupported media"
                logger.error(f"Playback error: {error_msg}")
                self.placeholder.setText(error_msg)
                self.placeholder.show()
                raise Exception(error_msg)
            
        except Exception as e:
            self.loading_spinner.stop()
            error_msg = f"Playback error: {str(e)}"
            logger.error(error_msg)
            self.placeholder.setText(error_msg)
            self.placeholder.show()
            raise e
    
    def _on_playing(self):
        """Handle media starting to play"""
        self.loading_spinner.stop()
        self.seek_bar.setEnabled(True)
        self.update_timer.start()
    
    def _handle_playback_error(self):
        """Handle VLC playback errors"""
        self.loading_spinner.stop()
        error_msg = "Stream playback failed - please check the URL and try again"
        logger.error(error_msg)
        self.placeholder.setText(error_msg)
        self.placeholder.show()
        
    def stop(self):
        if self.vlc_available:
            if self.fullscreen_window:
                self._exit_fullscreen()
            self.player.stop()
            self.loading_spinner.stop()
            self.placeholder.show()
            self.seek_bar.setEnabled(False)
            self.update_timer.stop()
            self.current_time_label.setText("00:00:00")
            self.duration_label.setText("00:00:00")
            self.seek_bar.setValue(0)
        
    def pause(self):
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
        if not self.vlc_available:
            return False
        try:
            return self.player.get_state() == self.vlc.State.Paused
        except Exception:
            return False 
    
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Handle double click for fullscreen toggle"""
        if not self.vlc_available or not self.player.is_playing():
            return
            
        if self.fullscreen_window is None:
            self.fullscreen_window = FullscreenWindow(self)
            self.fullscreen_window.destroyed.connect(self._on_fullscreen_closed)
        else:
            self._exit_fullscreen()
    
    def _exit_fullscreen(self):
        if self.fullscreen_window:
            # Restore video to main window
            if sys.platform == "win32":
                self.player.set_hwnd(self.winId())
            elif sys.platform.startswith('linux'):
                self.player.set_xwindow(self.winId())
            elif sys.platform == "darwin":
                self.player.set_nsobject(int(self.winId()))
            
            self.fullscreen_window.close()
            self.fullscreen_window = None
    
    def _on_fullscreen_closed(self):
        self._exit_fullscreen() 
    
    def keyPressEvent(self, event):
        """Handle ESC key to exit fullscreen"""
        if event.key() == Qt.Key.Key_Escape and self.fullscreen_window:
            self._exit_fullscreen()
    
    def resizeEvent(self, event):
        """Handle resize to keep spinner centered"""
        super().resizeEvent(event)
        # Center the spinner
        self.loading_spinner.move(
            (self.width() - self.loading_spinner.width()) // 2,
            (self.height() - self.loading_spinner.height()) // 2
        ) 
    
    def _format_time(self, ms):
        """Convert milliseconds to HH:MM:SS format"""
        s = ms // 1000
        h = s // 3600
        s = s % 3600
        m = s // 60
        s = s % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
    
    def _seek_bar_pressed(self):
        """Handle seek bar being pressed"""
        if self.vlc_available:
            self.update_timer.stop()
    
    def _seek_bar_released(self):
        """Handle seek bar being released"""
        if not self.vlc_available or not self.player.is_playing():
            return
        
        try:
            # Get the position as a percentage (0-1)
            position = self.seek_bar.value() / 1000.0
            
            # Set the position
            if self.player.is_seekable():
                self.player.set_position(position)
                # Force an immediate update of the time display
                current_time = int(position * self.player.get_length())
                self.current_time_label.setText(self._format_time(current_time))
            else:
                logger.warning("Media is not seekable")
                # Reset the seek bar to current position
                current_pos = int(self.player.get_position() * 1000)
                self.seek_bar.setValue(current_pos)
        except Exception as e:
            logger.error(f"Error while seeking: {str(e)}")
            # Reset the seek bar to current position
            current_pos = int(self.player.get_position() * 1000)
            self.seek_bar.setValue(current_pos)
    
    def _update_seek_bar(self):
        """Update seek bar position and time labels"""
        if not self.vlc_available or not self.player.is_playing():
            return
        
        # Get current time and duration in milliseconds
        current_time = self.player.get_time()
        duration = self.player.get_length()
        
        if duration > 0:
            # Update seek bar (use position 0-1000 for better precision)
            position = int(self.player.get_position() * 1000)
            self.seek_bar.setMaximum(1000)
            if not self.seek_bar.isSliderDown():  # Only update if user is not dragging
                self.seek_bar.setValue(position)
            
            # Update time labels
            self.current_time_label.setText(self._format_time(current_time))
            self.duration_label.setText(self._format_time(duration))
    
    def _handle_playback_error(self):
        """Handle VLC playback errors"""
        self.loading_spinner.stop()
        error_msg = "Stream playback failed - please check the URL and try again"
        logger.error(error_msg)
        self.placeholder.setText(error_msg)
        self.placeholder.show()
        
    def stop(self):
        if self.vlc_available:
            if self.fullscreen_window:
                self._exit_fullscreen()
            self.player.stop()
            self.loading_spinner.stop()
            self.placeholder.show()
            self.seek_bar.setEnabled(False)
            self.update_timer.stop()
            self.current_time_label.setText("00:00:00")
            self.duration_label.setText("00:00:00")
            self.seek_bar.setValue(0) 
    
    def _on_time_changed(self, event):
        """Handle time change events from VLC"""
        if not self.vlc_available or not self.player.is_playing():
            return
        
        current_time = self.player.get_time()
        duration = self.player.get_length()
        
        if duration > 0:
            # Update seek bar (use position 0-1000 for better precision)
            position = int(self.player.get_position() * 1000)
            self.seek_bar.setMaximum(1000)
            if not self.seek_bar.isSliderDown():  # Only update if user is not dragging
                self.seek_bar.setValue(position)
            
            # Update time labels
            self.current_time_label.setText(self._format_time(current_time))
            self.duration_label.setText(self._format_time(duration))
    
    def _on_length_changed(self, event):
        """Handle duration change events from VLC"""
        if not self.vlc_available:
            return
        
        duration = self.player.get_length()
        if duration > 0:
            self.duration_label.setText(self._format_time(duration)) 