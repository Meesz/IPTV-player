from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QListWidget,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.models import Program


class EPGWidget(QFrame):
    """A widget to display the Electronic Program Guide (EPG)."""

    def __init__(self):
        super().__init__()
        self.setObjectName("epg_widget")
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setMinimumHeight(280)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        heading = QLabel("Now / Next")
        heading.setObjectName("panel_heading")
        layout.addWidget(heading)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(8)

        self.current_title = QLabel("No program information")
        self.current_title.setObjectName("current_title")
        self.current_title.setWordWrap(True)
        scroll_layout.addWidget(self.current_title)

        self.current_time = QLabel("Load EPG data to see live scheduling.")
        self.current_time.setObjectName("current_time")
        scroll_layout.addWidget(self.current_time)

        self.state_hint = QLabel("")
        self.state_hint.setObjectName("placeholder_hint")
        self.state_hint.setWordWrap(True)
        self.state_hint.hide()
        scroll_layout.addWidget(self.state_hint)

        self.description = QLabel()
        self.description.setObjectName("player_meta")
        self.description.setWordWrap(True)
        scroll_layout.addWidget(self.description)

        upcoming_heading = QLabel("Coming Up")
        upcoming_heading.setObjectName("panel_heading")
        scroll_layout.addWidget(upcoming_heading)

        self.upcoming_list = QListWidget()
        self.upcoming_list.setObjectName("upcoming_list")
        self.upcoming_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        scroll_layout.addWidget(self.upcoming_list)

        scroll_area = QScrollArea()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        layout.addWidget(scroll_area)

    def clear(self) -> None:
        self.current_title.setText("No program information")
        self.current_time.setText("Load EPG data to see live scheduling.")
        self.state_hint.setText("")
        self.state_hint.hide()
        self.description.setText("")
        self.upcoming_list.clear()
        self.upcoming_list.addItem("No upcoming schedule available.")

    def set_loading_state(self, message: str) -> None:
        self.current_title.setText("Refreshing program guide")
        self.current_time.setText(message)
        self.state_hint.setText("Schedule data will appear here once the refresh finishes.")
        self.state_hint.show()
        self.description.setText("")
        self.upcoming_list.clear()
        self.upcoming_list.addItem("Loading schedule data...")

    def set_empty_state(self, title: str, detail: str) -> None:
        self.current_title.setText(title)
        self.current_time.setText(detail)
        self.state_hint.setText("")
        self.state_hint.hide()
        self.description.setText("")
        self.upcoming_list.clear()
        self.upcoming_list.addItem("No upcoming schedule available.")

    def set_current_program(self, program: Program | None) -> None:
        if not program:
            self.clear()
            return

        time_str = (
            f"{self._format_display_time(program.start_time)} - "
            f"{self._format_display_time(program.end_time)}"
        )
        self.current_title.setText(program.title)
        self.current_time.setText(time_str)
        self.state_hint.setText("")
        self.state_hint.hide()
        self.description.setText(program.description or "No program description available.")

    def set_upcoming_programs(self, programs: list[Program]) -> None:
        self.upcoming_list.clear()
        if not programs:
            self.upcoming_list.addItem("No upcoming schedule available.")
            return
        for program in programs:
            time_str = self._format_display_time(program.start_time)
            self.upcoming_list.addItem(f"{time_str}  {program.title}")

    @staticmethod
    def _format_display_time(value: datetime) -> str:
        if value.tzinfo is None:
            return value.strftime("%H:%M")
        return value.astimezone().strftime("%H:%M")
