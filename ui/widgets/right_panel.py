from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from core.models import Channel, Program
from ui.widgets.player_widget import PlayerWidget


class RightPanel(QFrame):
    """A panel containing the video player and playback controls."""

    def __init__(self):
        super().__init__()
        self.setObjectName("player_panel")
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setup_ui()

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        self.now_playing_card = QFrame()
        self.now_playing_card.setObjectName("now_playing_card")
        now_layout = QVBoxLayout(self.now_playing_card)
        now_layout.setContentsMargins(18, 18, 18, 18)
        now_layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        heading = QLabel("Now Playing")
        heading.setObjectName("panel_heading")
        top_row.addWidget(heading)
        top_row.addStretch()

        self.playback_state_chip = QLabel("Idle")
        self.playback_state_chip.setObjectName("playback_state_chip")
        self.playback_state_chip.setProperty("stateTone", "default")
        top_row.addWidget(self.playback_state_chip)
        now_layout.addLayout(top_row)

        self.channel_title_label = QLabel("Nothing selected")
        self.channel_title_label.setObjectName("player_channel_title")
        now_layout.addWidget(self.channel_title_label)

        self.channel_meta_label = QLabel("Load a playlist and pick a channel to begin.")
        self.channel_meta_label.setObjectName("player_meta")
        self.channel_meta_label.setWordWrap(True)
        now_layout.addWidget(self.channel_meta_label)

        self.program_title_label = QLabel("Program information appears here when EPG is available.")
        self.program_title_label.setObjectName("player_program_title")
        self.program_title_label.setWordWrap(True)
        now_layout.addWidget(self.program_title_label)

        self.playback_detail_label = QLabel("Awaiting stream selection.")
        self.playback_detail_label.setObjectName("player_meta")
        self.playback_detail_label.setWordWrap(True)
        now_layout.addWidget(self.playback_detail_label)

        layout.addWidget(self.now_playing_card)

        self.player_surface = QFrame()
        self.player_surface.setObjectName("player_surface")
        player_layout = QVBoxLayout(self.player_surface)
        player_layout.setContentsMargins(14, 14, 14, 14)
        player_layout.setSpacing(12)

        self.player_widget = PlayerWidget()
        player_layout.addWidget(self.player_widget)

        layout.addWidget(self.player_surface, stretch=1)

        self.control_bar = QFrame()
        self.control_bar.setObjectName("control_bar")
        controls_layout = QHBoxLayout(self.control_bar)
        controls_layout.setContentsMargins(14, 12, 14, 12)
        controls_layout.setSpacing(10)

        self.play_button = QPushButton("Play")
        self.play_button.setProperty("accent", True)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setProperty("ghost", True)
        self.favorite_button = QPushButton("Favorite")
        self.favorite_button.setProperty("ghost", True)
        self.favorite_button.setEnabled(False)
        self.volume_label = QLabel("Volume")
        self.volume_label.setObjectName("player_meta")
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)

        controls_layout.addWidget(self.play_button)
        controls_layout.addWidget(self.stop_button)
        controls_layout.addSpacing(6)
        controls_layout.addWidget(self.volume_label)
        controls_layout.addWidget(self.volume_slider, stretch=1)
        controls_layout.addSpacing(6)
        controls_layout.addWidget(self.favorite_button)

        layout.addWidget(self.control_bar)

    def set_playback_state(self, state: str, detail: str = "") -> None:
        titles = {
            "idle": "Idle",
            "connecting": "Connecting",
            "buffering": "Buffering",
            "playing": "Live",
            "reconnecting": "Reconnecting",
            "error": "Error",
        }
        tones = {
            "idle": "default",
            "connecting": "warning",
            "buffering": "warning",
            "playing": "success",
            "reconnecting": "warning",
            "error": "error",
        }
        self.playback_state_chip.setText(titles.get(state, state.title()))
        self.playback_state_chip.setProperty("stateTone", tones.get(state, "default"))
        self.playback_state_chip.style().unpolish(self.playback_state_chip)
        self.playback_state_chip.style().polish(self.playback_state_chip)
        if detail:
            self.playback_detail_label.setText(detail)

    def set_now_playing(
        self,
        channel: Channel | None,
        program: Program | None,
        playlist_path: str = "",
    ) -> None:
        if not channel:
            self.channel_title_label.setText("Nothing selected")
            self.channel_meta_label.setText("Load a playlist and pick a channel to begin.")
            self.program_title_label.setText(
                "Program information appears here when EPG is available."
            )
            self.playback_detail_label.setText("Awaiting stream selection.")
            return

        self.channel_title_label.setText(channel.name)
        playlist_name = Path(playlist_path).name if playlist_path else "Current source"
        meta_parts = [playlist_name]
        if channel.group:
            meta_parts.append(channel.group)
        self.channel_meta_label.setText(" / ".join(meta_parts))
        if program:
            schedule = f"{program.start_time.strftime('%H:%M')} - {program.end_time.strftime('%H:%M')}"
            self.program_title_label.setText(f"{program.title} ({schedule})")
        else:
            self.program_title_label.setText("No live guide information for this channel.")

    def set_source_context(self, playlist_path: str) -> None:
        playlist_name = Path(playlist_path).name if playlist_path else "No playlist loaded"
        self.channel_title_label.setText("Ready to Play")
        self.channel_meta_label.setText(playlist_name)
        self.program_title_label.setText("Choose a channel from the library to start playback.")
