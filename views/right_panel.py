"""
Module containing the RightPanel widget for video playback and controls.
"""

from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSlider,
    QLabel,
)
from PyQt6.QtCore import Qt
from views.player_widget import PlayerWidget


class RightPanel(QFrame):
    """A panel containing the video player and playback controls."""

    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)

        # Add player widget
        self.player_widget = PlayerWidget()
        layout.addWidget(self.player_widget)

        # Add playback controls
        controls_layout = QHBoxLayout()

        self.play_button = QPushButton("Play/Pause")
        self.stop_button = QPushButton("Stop")
        self.favorite_button = QPushButton("★")
        self.favorite_button.setCheckable(True)

        controls_layout.addWidget(self.play_button)
        controls_layout.addWidget(self.stop_button)
        controls_layout.addWidget(self.favorite_button)

        # Add volume control
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("Volume:"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        volume_layout.addWidget(self.volume_slider)

        # Add controls to layout
        layout.addLayout(controls_layout)
        layout.addLayout(volume_layout)
