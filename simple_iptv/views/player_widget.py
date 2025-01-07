import sys
import os
import ctypes
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
        self.vlc_available = False
        self._init_vlc()
    
    def _init_vlc(self):
        try:
            # Try to determine Python architecture
            is_64bits = sys.maxsize > 2**32
            
            # Set VLC plugin path based on architecture
            if sys.platform == "win32":
                if is_64bits:
                    vlc_path = "C:\\Program Files\\VideoLAN\\VLC"
                else:
                    vlc_path = "C:\\Program Files (x86)\\VideoLAN\\VLC"
                
                if not os.path.exists(vlc_path):
                    self.placeholder.setText(
                        f"Error: VLC not found in {vlc_path}\n"
                        f"Please install {'64' if is_64bits else '32'}-bit VLC"
                    )
                    return
                
                # Add VLC directory to PATH
                os.environ['PATH'] = vlc_path + ';' + os.environ['PATH']
                
                # Try to load VLC DLL directly
                try:
                    dll_path = os.path.join(vlc_path, 'libvlc.dll')
                    ctypes.CDLL(dll_path)
                except Exception as e:
                    self.placeholder.setText(
                        f"Error loading VLC: {str(e)}\n"
                        f"Python is {'64' if is_64bits else '32'}-bit\n"
                        "Make sure VLC architecture matches Python"
                    )
                    return
            
            # Import VLC
            import vlc
            
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
            
        media = self.instance.media_new(url)
        self.player.set_media(media)
        result = self.player.play()
        
        # Check if playback started successfully
        if result == -1:  # VLC returns -1 on error
            error_msg = "VLC is unable to open the MRL"
            print(f"Playback error: {error_msg}")
            raise Exception(error_msg)
        
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
        
    def is_paused(self) -> bool:
        if not self.vlc_available:
            return False
        return self.player.get_state() == vlc.State.Paused 