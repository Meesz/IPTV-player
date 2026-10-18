from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QListWidget, QListWidgetItem, QSizePolicy, QVBoxLayout

from core.models import Program
from ui.utils.time_format import format_display_time


class EPGWidget(QFrame):
    """Compact "Up next" column; the current program is shown by the now-playing block."""

    def __init__(self):
        super().__init__()
        self.setObjectName("epg_widget")
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)

        self.heading = QLabel("UP NEXT")
        self.heading.setObjectName("panel_heading")
        self.heading.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.heading)

        self.status_label = QLabel("")
        self.status_label.setObjectName("placeholder_hint")
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.status_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout.addWidget(self.status_label)

        self.upcoming_list = QListWidget()
        self.upcoming_list.setObjectName("upcoming_list")
        self.upcoming_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.upcoming_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.upcoming_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.upcoming_list.setWordWrap(False)
        self.upcoming_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.upcoming_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.upcoming_list, stretch=100)
        layout.addStretch(1)  # keeps heading and status line top-aligned while the list is hidden

        self.clear()

    def _show_status(self, text: str) -> None:
        self.upcoming_list.clear()
        self.upcoming_list.hide()
        self.status_label.setText(text)
        self.status_label.show()

    def clear(self) -> None:
        self._show_status("Select a channel to see what's on next.")

    def set_loading_state(self, message: str) -> None:
        self._show_status(message or "Refreshing program guide...")

    def set_empty_state(self, title: str, detail: str) -> None:
        self._show_status(f"{title}\n{detail}" if detail else title)

    def set_current_program(self, program: Program | None) -> None:
        """The running program is rendered elsewhere; only reset this column's state."""
        if not program:
            self.clear()
            return
        self.status_label.setText("")
        self.status_label.hide()

    def set_upcoming_programs(self, programs: list[Program]) -> None:
        if not programs:
            self._show_status("No upcoming schedule available.")
            return
        self.upcoming_list.clear()
        for program in programs:
            time_str = format_display_time(program.start_time)
            item = QListWidgetItem(f"{time_str}  {program.title}")
            item.setToolTip(program.title)
            self.upcoming_list.addItem(item)
        self.status_label.setText("")
        self.status_label.hide()
        self.upcoming_list.show()
