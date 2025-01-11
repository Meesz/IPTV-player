"""
Module containing the RightPanel widget for video playback and controls.
"""
# pylint: disable=no-name-in-module
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSlider,
)
from PyQt6.QtCore import Qt
from views.player_widget import PlayerWidget


class RightPanel(QFrame):
    """A panel containing the video player and playback controls."""

    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setup_ui()

    def setup_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)

        # Player widget
        self.player_widget = PlayerWidget()
        layout.addWidget(self.player_widget)

        # Controls layout
        self.controls_layout = QHBoxLayout()

        # Add existing controls
        self.play_button = QPushButton("Play")
        self.stop_button = QPushButton("Stop")
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.favorite_button = QPushButton("Favorite")

        self.controls_layout.addWidget(self.play_button)
        self.controls_layout.addWidget(self.stop_button)
        self.controls_layout.addWidget(self.volume_slider)
        self.controls_layout.addWidget(self.favorite_button)

        layout.addLayout(self.controls_layout)
