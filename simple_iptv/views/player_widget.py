import sys
import os
import ctypes
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMouseEvent
from .loading_spinner import LoadingSpinner

class FullscreenWindow(QWidget):
    def __init__(self, player_widget):
        super().__init__()
        self.player_widget = player_widget
        self.player = player_widget.player  # Get the VLC player instance
        
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        
        # Set black background
        self.setStyleSheet("background-color: black;")
        
        # Show window first
        self.showFullScreen()
        
        # Update VLC rendering target after window is shown
        if self.player_widget.vlc_available:
            if sys.platform == "win32":
                self.player.set_hwnd(self.winId())
            elif sys.platform.startswith('linux'):
                self.player.set_xwindow(self.winId())
            elif sys.platform == "darwin":
                self.player.set_nsobject(int(self.winId()))
    
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        self.close()
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

class PlayerWidget(QFrame):
    def __init__(self):
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
        self.vlc_available = False
        self._init_vlc()
        
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
                    self.placeholder.setText(
                        f"Error: VLC not found in {vlc_path}\n"
                        f"Please install {'64' if is_64bits else '32'}-bit VLC"
                    )
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
                '--sout-mux-caching=300'   # 300ms mux cache
            )
            
            self.player = self.instance.media_player_new()
            
            # Set up the window for VLC playback
            if sys.platform == "win32":
                self.player.set_hwnd(self.winId())
            elif sys.platform.startswith('linux'):
                self.player.set_xwindow(self.winId())
            elif sys.platform == "darwin":
                self.player.set_nsobject(int(self.winId()))
            
            # Set optimized media options
            self.player.set_role(vlc.MediaPlayerRole.Video)
            self.player.video_set_key_input(False)
            self.player.video_set_mouse_input(False)
            
            self.vlc_available = True
            print("VLC initialized successfully")
            
        except Exception as e:
            error_msg = (
                f"Error initializing VLC: {str(e)}\n"
                f"Python is {'64' if is_64bits else '32'}-bit\n"
                "Make sure you have the correct VLC version installed"
            )
            print(error_msg)
            self.placeholder.setText(error_msg)
            self.vlc_available = False
    
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
                lambda x: self.loading_spinner.stop()
            )
            events.event_attach(
                self.vlc.EventType.MediaPlayerEncounteredError,
                lambda x: self.loading_spinner.stop()
            )
            
            self.player.set_media(media)
            result = self.player.play()
            
            if result == -1:
                self.loading_spinner.stop()
                error_msg = "VLC is unable to open the MRL"
                print(f"Playback error: {error_msg}")
                raise Exception(error_msg)
            
        except Exception as e:
            self.loading_spinner.stop()
            self.placeholder.show()
            raise e
    
    def stop(self):
        if self.vlc_available:
            if self.fullscreen_window:
                self._exit_fullscreen()
            self.player.stop()
            self.loading_spinner.stop()
            self.placeholder.show()
        
    def pause(self):
        if self.vlc_available:
            self.player.pause()
        
    def set_volume(self, volume: int):
        if self.vlc_available:
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
        """Handle fullscreen window being closed"""
        self._exit_fullscreen()
    
    def keyPressEvent(self, event):
        """Handle ESC key to exit fullscreen"""
        if event.key() == Qt.Key.Key_Escape and self.is_fullscreen:
            self.window().showNormal()
            self.is_fullscreen = False 
    
    def resizeEvent(self, event):
        """Handle resize to keep spinner centered"""
        super().resizeEvent(event)
        # Center the spinner
        self.loading_spinner.move(
            (self.width() - self.loading_spinner.width()) // 2,
            (self.height() - self.loading_spinner.height()) // 2
        ) 