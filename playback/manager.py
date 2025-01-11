"""
Manages the playback of channels in Picture-in-Picture mode.
"""

from typing import Optional

# pylint: disable=no-name-in-module
from PyQt6.QtCore import QObject, pyqtSignal
from views.vlc_manager import VLCManager
from .pip_window import PiPWindow


class PlaybackManager(QObject):
    """
    Manages the playback of channels in Picture-in-Picture mode.
    """

    pip_started = pyqtSignal()
    pip_ended = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Ensure VLC is initialized
        success, error = VLCManager.initialize()
        if not success:
            raise RuntimeError(f"Failed to initialize VLC: {error}")

        self.pip_window: Optional[PiPWindow] = None
        self.main_window = parent

    def start_pip(self, channel_name: str, url: str):
        """Start Picture-in-Picture playback"""
        print(f"PlaybackManager: Starting PiP for {channel_name}")  # Debug

        # Pause the main player
        if self.main_window and self.main_window.player_controller:
            self.main_window.player_controller.window.player_widget.pause()

        if not self.pip_window:
            self.pip_window = PiPWindow()
            self.pip_window.stop_btn.clicked.connect(self.stop_pip)

        self.pip_window.show()
        print(f"PlaybackManager: Playing URL: {url}")  # Debug
        self.pip_window.play(url)
        self.pip_started.emit()

    def stop_pip(self):
        """Stop Picture-in-Picture playback"""
        if self.pip_window:
            self.pip_window.cleanup()  # Clean up VLC resources first
            self.pip_window.close()
            self.pip_window = None
            self.pip_ended.emit()

            # Resume the main player
            if self.main_window and self.main_window.player_controller:
                self.main_window.player_controller.window.player_widget.pause()  # Toggle pause again to resume
