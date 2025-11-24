from dataclasses import dataclass
from enum import Enum, auto
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt, QTimer

class NotificationType(Enum):
    INFO = auto()
    SUCCESS = auto()
    WARNING = auto()
    ERROR = auto()

@dataclass
class NotificationStyle:
    background: str
    border: str
    text_color: str

class NotificationWidget(QLabel):
    STYLES = {
        NotificationType.INFO: NotificationStyle("#2196F3", "#1976D2", "#FFFFFF"),
        NotificationType.SUCCESS: NotificationStyle("#4CAF50", "#388E3C", "#FFFFFF"),
        NotificationType.WARNING: NotificationStyle("#FFC107", "#FFA000", "#000000"),
        NotificationType.ERROR: NotificationStyle("#F44336", "#D32F2F", "#FFFFFF"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            padding: 10px;
            border-radius: 5px;
            font-weight: bold;
        """)
        self.hide()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.hide)

    def show_message(self, message: str, notification_type: NotificationType, duration: int = 3000):
        style = self.STYLES[notification_type]
        self.setStyleSheet(f"""
            background-color: {style.background};
            border: 1px solid {style.border};
            color: {style.text_color};
            padding: 10px;
            border-radius: 5px;
            font-weight: bold;
        """)

        self.setText(message)
        self.adjustSize()
        self.show()

        parent = self.parent()
        if parent:
            parent_rect = parent.rect()
            self.move((parent_rect.width() - self.width()) // 2, 20)

        self.timer.start(duration)
