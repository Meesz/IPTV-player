from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout

from core.models import Channel, Program
from ui.utils.time_format import format_display_time
from ui.widgets.player_widget import PlayerWidget


class RightPanel(QFrame):
    """A panel containing the video player and playback controls."""

    def __init__(self):
        super().__init__()
        self.setObjectName("player_panel")
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self._current_stream_url = ""
        self.setup_ui()

    def setup_ui(self) -> None:  # noqa: PLR0915  (Qt UI builder; pre-existing size)
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

        self.program_description_label = QLabel("")
        self.program_description_label.setObjectName("player_meta")
        self.program_description_label.setWordWrap(True)
        now_layout.addWidget(self.program_description_label)

        self.playback_detail_label = QLabel("")
        self.playback_detail_label.setObjectName("player_meta")
        self.playback_detail_label.setWordWrap(True)
        self.playback_detail_label.hide()
        now_layout.addWidget(self.playback_detail_label)

        layout.addWidget(self.now_playing_card)

        self.player_surface = QFrame()
        self.player_surface.setObjectName("player_surface")
        player_layout = QVBoxLayout(self.player_surface)
        player_layout.setContentsMargins(0, 0, 0, 0)
        player_layout.setSpacing(0)

        self.player_widget = PlayerWidget()
        player_layout.addWidget(self.player_widget)

        layout.addWidget(self.player_surface, stretch=1)

        self.control_bar = QFrame()
        self.control_bar.setObjectName("control_bar")
        controls_layout = QVBoxLayout(self.control_bar)
        controls_layout.setContentsMargins(14, 12, 14, 12)
        controls_layout.setSpacing(10)

        transport_row = QHBoxLayout()
        transport_row.setContentsMargins(0, 0, 0, 0)
        transport_row.setSpacing(10)

        self.play_button = QPushButton("Play")
        self.play_button.setProperty("accent", True)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setProperty("ghost", True)
        self.retry_button = QPushButton("Retry")
        self.retry_button.setProperty("ghost", True)
        self.mute_button = QPushButton("Mute")
        self.mute_button.setProperty("ghost", True)
        self.mute_button.setCheckable(True)
        self.favorite_button = QPushButton("Favorite")
        self.favorite_button.setProperty("ghost", True)
        self.favorite_button.setCheckable(True)
        self.favorite_button.setEnabled(False)
        self.fullscreen_button = QPushButton("Fullscreen")
        self.fullscreen_button.setProperty("ghost", True)

        for widget in (
            self.play_button,
            self.stop_button,
            self.retry_button,
            self.mute_button,
            self.favorite_button,
            self.fullscreen_button,
        ):
            transport_row.addWidget(widget)
        transport_row.addStretch()
        controls_layout.addLayout(transport_row)

        utility_row = QHBoxLayout()
        utility_row.setContentsMargins(0, 0, 0, 0)
        utility_row.setSpacing(10)

        self.volume_label = QLabel("Volume")
        self.volume_label.setObjectName("player_meta")
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_value_label = QLabel("100%")
        self.volume_value_label.setObjectName("player_meta")
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        self.copy_url_button = QPushButton("Copy URL")
        self.copy_url_button.setProperty("ghost", True)
        self.copy_url_button.setEnabled(False)
        self.info_button = QPushButton("Channel Info")
        self.info_button.setProperty("ghost", True)

        utility_row.addWidget(self.volume_label)
        utility_row.addWidget(self.volume_slider, stretch=1)
        utility_row.addWidget(self.volume_value_label)
        utility_row.addWidget(self.copy_url_button)
        utility_row.addWidget(self.info_button)
        controls_layout.addLayout(utility_row)

        layout.addWidget(self.control_bar)

    def _on_volume_changed(self, value: int) -> None:
        self.volume_value_label.setText(f"{value}%")

    def set_muted(self, muted: bool) -> None:
        self.mute_button.setChecked(muted)
        self.volume_slider.setEnabled(not muted)

    def set_favorite(self, is_favorite: bool) -> None:
        self.favorite_button.setChecked(is_favorite)

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

        show_detail = state in ("reconnecting", "error", "buffering")
        self.playback_detail_label.setVisible(show_detail)
        if detail and show_detail:
            self.playback_detail_label.setText(detail)
        elif not show_detail:
            self.playback_detail_label.setText("")

    def set_now_playing(
        self,
        channel: Channel | None,
        program: Program | None,
        playlist_label: str = "",
    ) -> None:
        if not channel:
            self.channel_title_label.setText("Nothing selected")
            self.channel_meta_label.setText("Load a playlist and pick a channel to begin.")
            self.program_title_label.setText("Program information appears here when EPG is available.")
            self.program_description_label.setText("")
            self._current_stream_url = ""
            self.copy_url_button.setEnabled(False)
            return

        self._current_stream_url = channel.url
        self.channel_title_label.setText(channel.name)
        playlist_name = playlist_label or "Current source"
        meta_parts = [playlist_name]
        if channel.group:
            meta_parts.append(channel.group)
        if channel.epg_id:
            meta_parts.append(f"EPG {channel.epg_id}")
        self.channel_meta_label.setText(" / ".join(meta_parts))

        if program:
            schedule = f"{format_display_time(program.start_time)} - {format_display_time(program.end_time)}"
            self.program_title_label.setText(f"{program.title} ({schedule})")
            self.program_description_label.setText(program.description or "No program description available.")
        else:
            self.program_title_label.setText("No live guide information for this channel.")
            self.program_description_label.setText("Load EPG data to enrich channel context.")

        self.copy_url_button.setEnabled(bool(channel.url))

    def set_source_context(self, playlist_label: str) -> None:
        self._current_stream_url = ""
        playlist_name = playlist_label or "No playlist loaded"
        self.channel_title_label.setText("Ready to Play")
        self.channel_meta_label.setText(playlist_name)
        self.program_title_label.setText("Choose a channel from the library to start playback.")
        self.program_description_label.setText(
            "Playback details, source context, and EPG description will appear here."
        )
        self.copy_url_button.setEnabled(False)

    def set_stream_url(self, url: str) -> None:
        self._current_stream_url = url
        self.copy_url_button.setEnabled(bool(url))

    @property
    def current_stream_url(self) -> str:
        return self._current_stream_url
