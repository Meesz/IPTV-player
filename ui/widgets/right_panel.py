from PyQt6.QtCore import QEvent, QSize, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from core.models import Channel, Program
from ui.styles.icons import make_icon
from ui.styles.themes import Themes
from ui.utils.time_format import format_display_time
from ui.widgets.epg_widget import EPGWidget
from ui.widgets.player_widget import PlayerWidget

_ICON_SIZE = 18
_BUTTON_SIZE = QSize(34, 32)
_EPG_MIN_WIDTH = 180
_EPG_MAX_WIDTH = 320
_INFO_MAX_HEIGHT = 180


class ElidedLabel(QLabel):
    """Single-line label that elides its text to the available width.

    ``text()`` returns the text currently displayed (elided); ``full_text()`` the original.
    The full text is also exposed as the tooltip.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._full_text = ""
        self._head = ""
        self._suffix = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)
        self.setText(text)

    def full_text(self) -> str:
        return self._full_text

    def setText(self, text: str) -> None:
        self.set_text_with_suffix(text, "")

    def set_text_with_suffix(self, head: str, suffix: str) -> None:
        """Show ``head`` + ``suffix``; only ``head`` is elided so the suffix stays visible."""
        self._head = head
        self._suffix = suffix
        self._full_text = head + suffix
        self.setToolTip(self._full_text)
        self._apply_elision()

    def _apply_elision(self) -> None:
        metrics = self.fontMetrics()
        width = max(0, self.contentsRect().width())
        if self._suffix:
            suffix_width = metrics.horizontalAdvance(self._suffix)
            elided = metrics.elidedText(self._head, Qt.TextElideMode.ElideRight, max(0, width - suffix_width))
            elided += self._suffix
        else:
            elided = metrics.elidedText(self._head, Qt.TextElideMode.ElideRight, width)
        if elided != super().text():
            super().setText(elided)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_elision()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_elision()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._apply_elision()


class ClampedTextLabel(QLabel):
    """Word-wrapped label limited to ``max_lines`` lines, ending in an ellipsis when cut.

    ``text()`` returns the displayed (wrapped, possibly elided) text; ``full_text()`` the original.
    """

    def __init__(self, max_lines: int = 2, parent: QWidget | None = None):
        super().__init__(parent)
        self._max_lines = max_lines
        self._full_text = ""
        self.setWordWrap(False)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self._apply_clamp()

    def full_text(self) -> str:
        return self._full_text

    def setText(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self._apply_clamp()

    def _wrapped_lines(self, width: int) -> list[str]:
        metrics = self.fontMetrics()
        words = self._full_text.split()
        lines: list[str] = []
        current = ""
        for index, word in enumerate(words):
            candidate = f"{current} {word}" if current else word
            if current and metrics.horizontalAdvance(candidate) > width:
                if len(lines) == self._max_lines - 1:
                    # Last allowed line: fold the remaining text in and let elision cut it.
                    current = " ".join([current, *words[index:]])
                    break
                lines.append(metrics.elidedText(current, Qt.TextElideMode.ElideRight, width))
                current = word
            else:
                current = candidate
        if current:
            lines.append(metrics.elidedText(current, Qt.TextElideMode.ElideRight, width))
        return lines

    def _apply_clamp(self) -> None:
        metrics = self.fontMetrics()
        self.setFixedHeight(self._max_lines * metrics.lineSpacing() + 2)
        width = max(0, self.contentsRect().width())
        shown = "\n".join(self._wrapped_lines(width))
        if shown != super().text():
            super().setText(shown)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_clamp()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_clamp()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._apply_clamp()


def _overline(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("panel_heading")
    font = label.font()
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
    label.setFont(font)
    return label


class RightPanel(QFrame):
    """Video-first panel: player, one-row control bar and a flat now-playing block."""

    def __init__(self):
        super().__init__()
        self.setObjectName("player_panel")
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self._current_stream_url = ""
        self._theme_mode = "dark"
        self.setup_ui()
        self.set_theme_mode(self._theme_mode)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.player_surface = QFrame()
        self.player_surface.setObjectName("player_surface")
        player_layout = QVBoxLayout(self.player_surface)
        player_layout.setContentsMargins(0, 0, 0, 0)
        player_layout.setSpacing(0)

        self.player_widget = PlayerWidget()
        player_layout.addWidget(self.player_widget)
        layout.addWidget(self.player_surface, stretch=1)

        self._build_control_bar()
        layout.addWidget(self.control_bar)

        self._build_now_playing()
        layout.addWidget(self.now_playing_card)

    def _icon_button(self, name: str, tooltip: str, *, checkable: bool = False) -> QPushButton:
        button = QPushButton()
        button.setProperty("ghost", True)
        button.setProperty("iconOnly", True)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip.split(" (", maxsplit=1)[0])
        button.setCheckable(checkable)
        button.setFixedSize(_BUTTON_SIZE)
        button.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        button.setProperty("iconName", name)
        return button

    def _build_control_bar(self) -> None:
        self.control_bar = QFrame()
        self.control_bar.setObjectName("control_bar")
        bar = QHBoxLayout(self.control_bar)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(6)

        self.play_button = QPushButton("Play")
        self.play_button.setProperty("accent", True)
        self.play_button.setProperty("iconName", "play")
        self.play_button.setToolTip("Play (Space)")
        self.play_button.setAccessibleName("Play")
        self.play_button.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        self.play_button.setMinimumWidth(84)
        self.stop_button = self._icon_button("stop", "Stop")
        self.retry_button = self._icon_button("retry", "Retry stream")
        self.mute_button = self._icon_button("volume", "Mute (M)", checkable=True)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setMinimumWidth(80)
        self.volume_slider.setMaximumWidth(160)
        self.volume_slider.setAccessibleName("Volume")
        self.volume_value_label = QLabel("100%")
        self.volume_value_label.setObjectName("player_meta")
        self.volume_value_label.setMinimumWidth(36)
        self.volume_value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)

        self.favorite_button = self._icon_button("star", "Favorite", checkable=True)
        self.favorite_button.setEnabled(False)
        self.copy_url_button = self._icon_button("copy", "Copy stream URL")
        self.copy_url_button.setEnabled(False)
        self.info_button = self._icon_button("info", "Channel info")
        self.fullscreen_button = self._icon_button("fullscreen", "Fullscreen (F)")

        self.mute_button.toggled.connect(self._refresh_icons)
        self.favorite_button.toggled.connect(self._refresh_icons)

        for widget in (self.play_button, self.stop_button, self.retry_button):
            bar.addWidget(widget)
        bar.addSpacing(10)
        bar.addWidget(self.mute_button)
        bar.addWidget(self.volume_slider)
        bar.addWidget(self.volume_value_label)
        bar.addStretch(1)
        for widget in (self.favorite_button, self.copy_url_button, self.info_button, self.fullscreen_button):
            bar.addWidget(widget)

    def _build_now_playing(self) -> None:
        self.now_playing_card = QFrame()
        self.now_playing_card.setObjectName("now_playing_card")
        self.now_playing_card.setMaximumHeight(_INFO_MAX_HEIGHT)
        row = QHBoxLayout(self.now_playing_card)
        row.setContentsMargins(2, 4, 2, 0)
        row.setSpacing(16)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(3)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        top_row.addWidget(_overline("NOW PLAYING"))
        self.playback_state_chip = QLabel("Idle")
        self.playback_state_chip.setObjectName("playback_state_chip")
        self.playback_state_chip.setProperty("stateTone", "default")
        top_row.addWidget(self.playback_state_chip)
        top_row.addStretch(1)
        info.addLayout(top_row)

        self.channel_title_label = ElidedLabel("No channel selected")
        self.channel_title_label.setObjectName("player_channel_title")
        info.addWidget(self.channel_title_label)

        self.channel_meta_label = ElidedLabel("Pick a channel from the guide to start watching.")
        self.channel_meta_label.setObjectName("player_meta")
        info.addWidget(self.channel_meta_label)

        self.program_title_label = ElidedLabel("")
        self.program_title_label.setObjectName("player_program_title")
        info.addWidget(self.program_title_label)

        self.program_description_label = ClampedTextLabel(max_lines=2)
        self.program_description_label.setObjectName("player_meta")
        info.addWidget(self.program_description_label)

        self.playback_detail_label = ElidedLabel("")
        self.playback_detail_label.setObjectName("player_meta")
        self.playback_detail_label.hide()
        info.addWidget(self.playback_detail_label)
        info.addStretch(1)

        row.addLayout(info, stretch=3)

        self.epg_widget = EPGWidget()
        self.epg_widget.setMinimumWidth(_EPG_MIN_WIDTH)
        self.epg_widget.setMaximumWidth(_EPG_MAX_WIDTH)
        row.addWidget(self.epg_widget, stretch=2)

    def set_theme_mode(self, mode: str) -> None:
        self._theme_mode = mode
        self._refresh_icons()

    def _icon(self, name: str, color_key: str):
        mode = self._theme_mode
        return make_icon(
            name,
            Themes.color(mode, color_key),
            _ICON_SIZE,
            disabled_color=Themes.color(mode, "faint"),
        )

    def _refresh_icons(self, *_args) -> None:
        self.play_button.setIcon(self._icon("play", "accent_text"))
        self.stop_button.setIcon(self._icon("stop", "text"))
        self.retry_button.setIcon(self._icon("retry", "text"))
        self.mute_button.setIcon(
            self._icon("volume-muted", "accent") if self.mute_button.isChecked() else self._icon("volume", "text")
        )
        self.favorite_button.setIcon(
            self._icon("star-filled", "accent") if self.favorite_button.isChecked() else self._icon("star", "text")
        )
        self.copy_url_button.setIcon(self._icon("copy", "text"))
        self.info_button.setIcon(self._icon("info", "text"))
        self.fullscreen_button.setIcon(self._icon("fullscreen", "text"))

    def _on_volume_changed(self, value: int) -> None:
        self.volume_value_label.setText(f"{value}%")

    @staticmethod
    def _set_button_label(button: QPushButton, tooltip: str) -> None:
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip.split(" (", maxsplit=1)[0])

    def set_muted(self, muted: bool) -> None:
        self.mute_button.setChecked(muted)
        self.volume_slider.setEnabled(not muted)
        self._set_button_label(self.mute_button, "Unmute (M)" if muted else "Mute (M)")

    def set_favorite(self, is_favorite: bool) -> None:
        self.favorite_button.setChecked(is_favorite)
        self._set_button_label(self.favorite_button, "Remove from favorites" if is_favorite else "Add to favorites")

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
            "playing": "live",
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

    def _set_program_description(self, text: str) -> None:
        self.program_description_label.setText(text)
        self.program_description_label.setToolTip(text)

    def set_now_playing(
        self,
        channel: Channel | None,
        program: Program | None,
        playlist_label: str = "",
    ) -> None:
        if not channel:
            self.channel_title_label.setText("No channel selected")
            self.channel_meta_label.setText("Pick a channel from the guide to start watching.")
            self.program_title_label.setText("")
            self._set_program_description("")
            self._current_stream_url = ""
            self.copy_url_button.setEnabled(False)
            return

        self._current_stream_url = channel.url
        self.channel_title_label.setText(channel.name)
        meta_parts = [playlist_label or "Current source"]
        if channel.group:
            meta_parts.append(channel.group)
        if channel.epg_id:
            meta_parts.append(f"EPG {channel.epg_id}")
        self.channel_meta_label.setText(" · ".join(meta_parts))

        if program:
            schedule = f"{format_display_time(program.start_time)} - {format_display_time(program.end_time)}"
            self.program_title_label.set_text_with_suffix(program.title, f" · {schedule}")
            self._set_program_description(program.description or "")
        else:
            self.program_title_label.setText("No current program in the guide")
            self._set_program_description("")

        self.copy_url_button.setEnabled(bool(channel.url))

    def set_source_context(self, playlist_label: str) -> None:
        self._current_stream_url = ""
        if playlist_label:
            self.channel_title_label.setText("Ready to play")
            self.channel_meta_label.setText(playlist_label)
        else:
            self.channel_title_label.setText("No playlist loaded")
            self.channel_meta_label.setText("Open Sources to add one.")
        self.program_title_label.setText("")
        self._set_program_description("")
        self.copy_url_button.setEnabled(False)

    def set_stream_url(self, url: str) -> None:
        self._current_stream_url = url
        self.copy_url_button.setEnabled(bool(url))

    @property
    def current_stream_url(self) -> str:
        return self._current_stream_url
