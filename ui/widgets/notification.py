from dataclasses import dataclass
from enum import Enum, auto
import time

from PyQt6.QtCore import QEvent, QTimer, Qt
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
        self.timer.timeout.connect(self._advance_queue)
        self._queue: list[tuple[str, NotificationType, int]] = []
        self._recent_signatures: dict[tuple[str, NotificationType], float] = {}
        self._current_signature: tuple[str, NotificationType] | None = None
        if parent is not None:
            parent.installEventFilter(self)

    def show_message(
        self,
        message: str,
        notification_type: NotificationType,
        duration: int = 3000,
    ) -> None:
        signature = (message, notification_type)
        now = time.monotonic()
        if now - self._recent_signatures.get(signature, 0.0) < 1.5:
            return
        if self._current_signature == signature and self.isVisible():
            return
        if any(entry[:2] == signature for entry in self._queue):
            return
        if self.isVisible():
            self._queue.append((message, notification_type, duration))
            return

        self._display_message(message, notification_type, duration)

    def _display_message(
        self,
        message: str,
        notification_type: NotificationType,
        duration: int,
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
        self.raise_()
        self._reposition()
        self._current_signature = (message, notification_type)
        self._recent_signatures[self._current_signature] = time.monotonic()
        self.timer.start(duration)

    def _advance_queue(self) -> None:
        self.hide()
        self._current_signature = None
        if not self._queue:
            return
        message, notification_type, duration = self._queue.pop(0)
        self._display_message(message, notification_type, duration)

    def _reposition(self) -> None:
        parent = self.parent()
        if parent:
            parent_rect = parent.rect()
            self.move((parent_rect.width() - self.width()) // 2, 28)

    def eventFilter(self, watched, event):
        if watched is self.parent() and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Move,
            QEvent.Type.Show,
        } and self.isVisible():
            self._reposition()
        return super().eventFilter(watched, event)
