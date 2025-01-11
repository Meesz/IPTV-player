"""
Picture-in-Picture window for VLC playback.
"""

import sys

# pylint: disable=no-name-in-module
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSizeGrip,
    QFrame,
    QSizePolicy,
)
from views.vlc_manager import VLCManager
from utils.themes import Themes


class FullscreenPiP(QWidget):
    """Fullscreen window for PiP mode"""

    def __init__(self, pip_window):
        super().__init__()
        print("FullscreenPiP: Initializing")  # Debug
        self.pip_window = pip_window
        self.player = pip_window.player

        # Make window fullscreen
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("background-color: black;")

        # Enable mouse tracking
        self.setMouseTracking(True)

        print("FullscreenPiP: Showing fullscreen")  # Debug
        self.showFullScreen()

        # Update VLC rendering target
        self._update_vlc_rendering_target()

    def _update_vlc_rendering_target(self):
        """Update VLC rendering target based on platform"""
        print("FullscreenPiP: Updating VLC rendering target")  # Debug
        if sys.platform == "win32":
            self.player.set_hwnd(self.winId())
        elif sys.platform.startswith("linux"):
            self.player.set_xwindow(self.winId())
        elif sys.platform == "darwin":
            self.player.set_nsobject(int(self.winId()))

    def mouseDoubleClickEvent(self, event):
        """Handle double click to exit fullscreen"""
        print("FullscreenPiP: Double click detected")  # Debug
        self.close()

    def keyPressEvent(self, event):
        """Handle ESC key to exit fullscreen"""
        print("FullscreenPiP: Key press detected")  # Debug
        if event.key() == Qt.Key.Key_Escape:
            print("FullscreenPiP: ESC key pressed")  # Debug
            self.close()

    def resizeEvent(self, event):
        """Handle resize to update VLC rendering target"""
        super().resizeEvent(event)
        print("FullscreenPiP: Resize event")  # Debug
        self._update_vlc_rendering_target()


class PiPWindow(QFrame):
    """Picture-in-Picture window"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
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

        # Track fullscreen window
        self.fullscreen_window = None

        # Enable mouse tracking
        self.setMouseTracking(True)

    def cleanup(self):
        """Clean up VLC resources"""
        if hasattr(self, "player") and self.player:
            self.player.stop()
            self.player.release()
            self.player = None
        if hasattr(self, "instance") and self.instance:
            self.instance.release()
            self.instance = None

    def closeEvent(self, event):
        """Handle window close event"""
        self.cleanup()
        super().closeEvent(event)

    def setup_ui(self):
        """Setup UI elements"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)

        # Title bar with drag handle
        title_bar = QWidget()
        title_bar.setStyleSheet(
            """
            QWidget {
                background-color: #2d2d2d;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
        """
        )
        title_bar.setCursor(Qt.CursorShape.SizeAllCursor)  # Show move cursor
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(4, 4, 4, 4)

        # Add a label to show it's draggable
        drag_label = QPushButton("⋮⋮")  # Vertical dots to indicate draggable
        drag_label.setStyleSheet(
            """
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
        """
        )
        title_layout.addWidget(drag_label)
        title_layout.addStretch()

        # Video container with dark background
        self.video_container = QWidget()
        self.video_container.setStyleSheet(
            """
            QWidget {
                background-color: #000000;
                border: none;
            }
        """
        )
        self.video_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Controls container
        controls_container = QWidget()
        controls_container.setStyleSheet(
            """
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
        """
        )

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
        self.size_grip.setStyleSheet(
            """
            QSizeGrip {
                background-color: #2d2d2d;
                width: 16px;
                height: 16px;
            }
        """
        )
        self.controls_layout.addWidget(self.size_grip)

        # Add all components to main layout
        main_layout.addWidget(title_bar)
        main_layout.addWidget(self.video_container, 1)
        main_layout.addWidget(controls_container)

        # Set overall window style
        self.setStyleSheet(
            self.styleSheet()
            + """
            PiPWindow {
                background-color: #1a1a1a;
                border: 1px solid #404040;
                border-radius: 4px;
            }
        """
        )

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
        if hasattr(self, "player"):
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

    def mouseDoubleClickEvent(self, event):
        """Handle double click for fullscreen toggle"""
        print("PiPWindow: Double click detected")  # Debug

        if not hasattr(self, "player") or not self.player:
            print("PiPWindow: No player available")  # Debug
            return

        if not self.player.is_playing():
            print("PiPWindow: Player is not playing")  # Debug
            return

        print(
            f"PiPWindow: Fullscreen window exists: {self.fullscreen_window is not None}"
        )  # Debug

        if not self.fullscreen_window:
            print("PiPWindow: Creating fullscreen window")  # Debug
            self.fullscreen_window = FullscreenPiP(self)
            self.fullscreen_window.destroyed.connect(self._on_fullscreen_closed)
        else:
            print("PiPWindow: Exiting fullscreen")  # Debug
            self._exit_fullscreen()

    def _exit_fullscreen(self):
        """Exit fullscreen mode and restore video to PiP window"""
        print("PiPWindow: Executing _exit_fullscreen")  # Debug
        if self.fullscreen_window:
            print("PiPWindow: Restoring video to PiP window")  # Debug
            # Restore video to PiP window
            if sys.platform == "win32":
                self.player.set_hwnd(self.video_container.winId())
            elif sys.platform.startswith("linux"):
                self.player.set_xwindow(self.video_container.winId())
            elif sys.platform == "darwin":
                self.player.set_nsobject(int(self.video_container.winId()))

            print("PiPWindow: Closing fullscreen window")  # Debug
            self.fullscreen_window.close()
            self.fullscreen_window = None

    def _on_fullscreen_closed(self):
        """Callback for when the fullscreen window is closed"""
        self._exit_fullscreen()

    def keyPressEvent(self, event):
        """Handle ESC key to exit fullscreen"""
        if event.key() == Qt.Key.Key_Escape and self.fullscreen_window:
            self._exit_fullscreen()
