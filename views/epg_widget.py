"""
Module containing the EPG (Electronic Program Guide) widget.
"""

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


class EPGWidget(QFrame):
    """A widget to display the Electronic Program Guide (EPG)."""

    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setFixedHeight(300)
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(5)

        # Current program
        self.current_title = QLabel("No program information")
        self.current_title.setStyleSheet("font-weight: bold;")
        self.current_title.setWordWrap(True)
        scroll_layout.addWidget(self.current_title)

        self.current_time = QLabel()
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
        """Clear all EPG information."""
        self.clear_current_program()
        self.clear_upcoming_programs()

    def set_current_program(self, title, start_time, end_time, description=""):
        """Set the current program information.
        
        Args:
            title: Program title
            start_time: Start time (datetime)
            end_time: End time (datetime)
            description: Program description
        """
        if not title:
            self.clear_current_program()
            return
            
        # Format the time string
        time_str = f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}"
        
        # Update the UI components
        self.current_title.setText(title)
        self.current_time.setText(time_str)
        self.description.setText(description or "")

    def clear_current_program(self):
        """Clear the current program information."""
        self.current_title.setText("No program information")
        self.current_time.setText("")
        self.description.setText("")

    def add_upcoming_program(self, title, start_time, end_time, description=""):
        """Add an upcoming program to the list.
        
        Args:
            title: Program title
            start_time: Start time (datetime)
            end_time: End time (datetime)
            description: Program description (unused in list view)
        """
        if not title:
            return
            
        time_str = start_time.strftime("%H:%M")
        self.upcoming_list.addItem(f"{time_str} - {title}")

    def clear_upcoming_programs(self):
        """Clear the list of upcoming programs."""
        self.upcoming_list.clear()

    def update_current_program(self, title: str, time_str: str, description: str):
        """Update the current program information.
        
        Legacy method for backward compatibility.
        """
        self.current_title.setText(title)
        self.current_time.setText(time_str)
        self.description.setText(description)

    def set_upcoming_programs(self, programs: list):
        """Set the list of upcoming programs.
        
        Legacy method for backward compatibility.
        
        Args:
            programs: List of Program objects
        """
        self.upcoming_list.clear()
        for prog in programs:
            time_str = prog.start_time.strftime("%H:%M")
            self.upcoming_list.addItem(f"{time_str} - {prog.title}")
