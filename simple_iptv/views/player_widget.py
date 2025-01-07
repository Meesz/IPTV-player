import sys
import vlc
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt

class PlayerWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(400, 300)
        
        # Create layout
        self.layout = QVBoxLayout(self)
        
        # Create placeholder label
        self.placeholder = QLabel("No media playing")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.placeholder)
        
        # Initialize VLC
        try:
            self.instance = vlc.Instance()
            self.player = self.instance.media_player_new()
            
            # Set up the window for VLC playback
            if sys.platform == "win32":
                self.player.set_hwnd(self.winId())
            elif sys.platform.startswith('linux'):
                self.player.set_xwindow(self.winId())
            elif sys.platform == "darwin":
                self.player.set_nsobject(int(self.winId()))
                
            self.vlc_available = True
        except Exception:
            self.vlc_available = False
            self.placeholder.setText("Error: VLC not available")
            
    def play(self, url: str):
        if not self.vlc_available:
            return
            
        media = self.instance.media_new(url)
        self.player.set_media(media)
        self.player.play()
        self.placeholder.hide()
        
    def stop(self):
        if self.vlc_available:
            self.player.stop()
            self.placeholder.show()
        
    def pause(self):
        if self.vlc_available:
            self.player.pause()
        
    def set_volume(self, volume: int):
        if self.vlc_available:
            self.player.audio_set_volume(volume) 