"""
This module contains the NotificationWidget class, which is responsible for displaying notifications.
"""

from dataclasses import dataclass
from enum import Enum, auto

# pylint: disable=no-name-in-module
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt, QTimer


class NotificationType(Enum):
    """Enumeration for different types of notifications."""

    INFO = auto()
    SUCCESS = auto()
    WARNING = auto()
    ERROR = auto()


@dataclass
class NotificationStyle:
    """Data class to define the style attributes for a notification."""

    background: str
    border: str
    text_color: str


class NotificationWidget(QLabel):
    """A widget to display notifications with different styles and durations."""

    STYLES = {
        NotificationType.INFO: NotificationStyle("#2196F3", "#1976D2", "#FFFFFF"),
        NotificationType.SUCCESS: NotificationStyle("#4CAF50", "#388E3C", "#FFFFFF"),
        NotificationType.WARNING: NotificationStyle("#FFC107", "#FFA000", "#000000"),
        NotificationType.ERROR: NotificationStyle("#F44336", "#D32F2F", "#FFFFFF"),
    }

    def __init__(self, parent=None):
        """
        Initialize the NotificationWidget.

        Args:
            parent: The parent widget of this notification widget.
        """
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            """
            padding: 10px;
            border-radius: 5px;
            font-weight: bold;
        """
        )
        self.hide()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.hide)

    def show_message(self, message: str, type: NotificationType, duration: int = 3000):
        """
        Display a notification message with a specific style and duration.

        Args:
            message (str): The message to display.
            type (NotificationType): The type of notification to determine the style.
            duration (int): The duration in milliseconds for which the notification is displayed.
        """
        style = self.STYLES[type]
        self.setStyleSheet(
            f"""
            background-color: {style.background};
            border: 1px solid {style.border};
            color: {style.text_color};
            padding: 10px;
            border-radius: 5px;
            font-weight: bold;
        """
        )

        self.setText(message)
        self.adjustSize()
        self.show()

        # Position at the top center of the parent
        parent_rect = self.parent().rect()
        self.move((parent_rect.width() - self.width()) // 2, 20)

        self.timer.start(duration)
