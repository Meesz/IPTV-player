from dataclasses import dataclass
from enum import Enum, auto

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QLabel


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
        NotificationType.INFO: NotificationStyle("#183742", "#2e6e80", "#edf5f7"),
        NotificationType.SUCCESS: NotificationStyle("#17392d", "#2b8b68", "#effaf5"),
        NotificationType.WARNING: NotificationStyle("#43331a", "#b07f32", "#fff3de"),
        NotificationType.ERROR: NotificationStyle("#482028", "#b14858", "#fff1f3"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("notification_toast")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.hide()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.hide)

    def show_message(
        self,
        message: str,
        notification_type: NotificationType,
        duration: int = 3000,
    ) -> None:
        style = self.STYLES[notification_type]
        self.setStyleSheet(
            f"""
            QLabel#notification_toast {{
                background-color: {style.background};
                border: 1px solid {style.border};
                color: {style.text_color};
                padding: 12px 16px;
                border-radius: 14px;
                font-weight: 700;
            }}
            """
        )

        self.setText(message)
        self.adjustSize()
        self.show()

        parent = self.parent()
        if parent:
            parent_rect = parent.rect()
            self.move((parent_rect.width() - self.width()) // 2, 28)

        self.timer.start(duration)
