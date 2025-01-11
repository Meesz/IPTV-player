from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QWidget, 
    QVBoxLayout, 
    QHBoxLayout,
    QPushButton, 
    QSizeGrip,
    QFrame,
    QSizePolicy
)
from views.vlc_manager import VLCManager
from utils.themes import Themes

class PiPWindow(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Window | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.FramelessWindowHint
        )
        
        # Initialize drag tracking
        self.old_pos = None
        self.dragging = False
        self.player = None
        self.instance = None
        
        # Apply theme
        self.setStyleSheet(Themes.get_dark_theme())
        
        self.setup_ui()
        self.setup_player()
        
        # Set minimum and default size
        self.setMinimumSize(320, 180)
        self.resize(480, 270)

    def cleanup(self):
        """Clean up VLC resources"""
        if hasattr(self, 'player') and self.player:
            self.player.stop()
            self.player.release()
            self.player = None
        if hasattr(self, 'instance') and self.instance:
            self.instance.release()
            self.instance = None

    def closeEvent(self, event):
        """Handle window close event"""
        self.cleanup()
        super().closeEvent(event)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)
        
        # Title bar with drag handle
        title_bar = QWidget()
        title_bar.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
        """)
        title_bar.setCursor(Qt.CursorShape.SizeAllCursor)  # Show move cursor
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(4, 4, 4, 4)
        
        # Add a label to show it's draggable
        drag_label = QPushButton("⋮⋮")  # Vertical dots to indicate draggable
        drag_label.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #808080;
                font-size: 16px;
                padding: 2px 8px;
            }
            QPushButton:hover {
                color: #ffffff;
            }
        """)
        title_layout.addWidget(drag_label)
        title_layout.addStretch()
        
        # Video container with dark background
        self.video_container = QWidget()
        self.video_container.setStyleSheet("""
            QWidget {
                background-color: #000000;
                border: none;
            }
        """)
        self.video_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        
        # Controls container
        controls_container = QWidget()
        controls_container.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border-bottom-left-radius: 4px;
                border-bottom-right-radius: 4px;
            }
            QPushButton {
                min-width: 60px;
                padding: 4px 8px;
                background-color: #3d3d3d;
                border: none;
                border-radius: 2px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
            QPushButton:pressed {
                background-color: #2d2d2d;
            }
        """)
        
        self.controls_layout = QHBoxLayout(controls_container)
        self.controls_layout.setContentsMargins(4, 4, 4, 4)
        self.controls_layout.setSpacing(4)
        
        # Create buttons with icons
        self.play_pause_btn = QPushButton("⏸")
        self.stop_btn = QPushButton("⏹")
        
        self.controls_layout.addWidget(self.play_pause_btn)
        self.controls_layout.addWidget(self.stop_btn)
        self.controls_layout.addStretch()
        
        # Size grip
        self.size_grip = QSizeGrip(self)
        self.size_grip.setStyleSheet("""
            QSizeGrip {
                background-color: #2d2d2d;
                width: 16px;
                height: 16px;
            }
        """)
        self.controls_layout.addWidget(self.size_grip)
        
        # Add all components to main layout
        main_layout.addWidget(title_bar)
        main_layout.addWidget(self.video_container, 1)
        main_layout.addWidget(controls_container)
        
        # Set overall window style
        self.setStyleSheet(self.styleSheet() + """
            PiPWindow {
                background-color: #1a1a1a;
                border: 1px solid #404040;
                border-radius: 4px;
            }
        """)
        
    def setup_player(self):
        print("PiPWindow: Setting up player")  # Debug
        vlc = VLCManager._vlc
        print(f"PiPWindow: VLC instance: {vlc}")  # Debug
        if vlc:
            self.instance = vlc.Instance()
            self.player = self.instance.media_player_new()
            
            if self.video_container.winId():
                print(f"PiPWindow: Window ID: {self.video_container.winId()}")  # Debug
                self.player.set_hwnd(self.video_container.winId())
            
    def play(self, url):
        print(f"PiPWindow: Attempting to play {url}")  # Debug
        if hasattr(self, 'player'):
            print("PiPWindow: Player exists, creating media")  # Debug
            media = self.instance.media_new(url)
            self.player.set_media(media)
            self.player.play()
        else:
            print("PiPWindow: No player available!")  # Debug
        
    def mousePressEvent(self, event):
        # Only handle left button events
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if click is in title bar area
            if event.position().y() <= 30:  # Approximate title bar height
                self.dragging = True
                self.old_pos = event.globalPosition().toPoint()
        
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.old_pos = None
        
    def mouseMoveEvent(self, event):
        if self.dragging and self.old_pos is not None:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint() 