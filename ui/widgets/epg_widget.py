from datetime import datetime
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QWidget,
    QLabel,
    QListWidget,
    QScrollArea,
)
from PyQt6.QtCore import Qt
from core.models import Program

class EPGWidget(QFrame):
    """A widget to display the Electronic Program Guide (EPG)."""

    def __init__(self):
        super().__init__()
        self.setObjectName("epg_widget")
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setFixedHeight(300)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(5)

        # Current program
        self.current_title = QLabel("No program information")
        self.current_title.setObjectName("current_title")
        self.current_title.setWordWrap(True)
        scroll_layout.addWidget(self.current_title)

        self.current_time = QLabel()
        self.current_time.setObjectName("current_time")
        scroll_layout.addWidget(self.current_time)

        self.description = QLabel()
        self.description.setWordWrap(True)
        scroll_layout.addWidget(self.description)

        # Upcoming programs
        scroll_layout.addWidget(QLabel("Upcoming:"))
        self.upcoming_list = QListWidget()
        scroll_layout.addWidget(self.upcoming_list)

        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        layout.addWidget(scroll_area)

    def clear(self):
        self.current_title.setText("No program information")
        self.current_time.setText("")
        self.description.setText("")
        self.upcoming_list.clear()

    def set_current_program(self, program: Program):
        if not program:
            self.clear()
            return
            
        time_str = f"{program.start_time.strftime('%H:%M')} - {program.end_time.strftime('%H:%M')}"
        self.current_title.setText(program.title)
        self.current_time.setText(time_str)
        self.description.setText(program.description or "")

    def set_upcoming_programs(self, programs: list[Program]):
        self.upcoming_list.clear()
        for prog in programs:
            time_str = prog.start_time.strftime("%H:%M")
            self.upcoming_list.addItem(f"{time_str} - {prog.title}")
