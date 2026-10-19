import time
from enum import Enum, auto

from PyQt6.QtCore import QEvent, QPoint, QRect, Qt, QTimer
from PyQt6.QtWidgets import QLabel, QWidget


class NotificationType(Enum):
    INFO = auto()
    SUCCESS = auto()
    WARNING = auto()
    ERROR = auto()


_TONE_MAP = {
    NotificationType.INFO: "info",
    NotificationType.SUCCESS: "success",
    NotificationType.WARNING: "warning",
    NotificationType.ERROR: "error",
}


class NotificationWidget(QLabel):
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
        self._anchor: QWidget | None = None
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
        self.setProperty("stateTone", _TONE_MAP[notification_type])
        self.style().unpolish(self)
        self.style().polish(self)

        self.setText(message)
        max_w = max(240, self._available_rect().width() - 48)
        self.setMaximumWidth(max_w)
        self.setFixedWidth(min(self.sizeHint().width() + 32, max_w))
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

    def set_anchor(self, anchor: QWidget | None) -> None:
        """Place toasts at the bottom of ``anchor`` instead of the window bottom.

        Avoid anchoring to the native video surface: native child windows stack above
        alien sibling widgets, so a toast over the video would be hidden.
        """
        if self._anchor is not None:
            self._anchor.removeEventFilter(self)
        self._anchor = anchor
        if anchor is not None:
            anchor.installEventFilter(self)

    def _available_rect(self) -> QRect:
        parent = self.parent()
        if parent is None:
            return QRect(0, 0, 600, 400)
        if self._anchor is not None and self._anchor.isVisible():
            top_left = self._anchor.mapTo(parent, QPoint(0, 0))
            return QRect(top_left, self._anchor.size())
        return parent.rect()

    def _reposition(self) -> None:
        if self.parent() is None:
            return
        rect = self._available_rect()
        self.move(
            rect.left() + max(0, (rect.width() - self.width()) // 2),
            max(rect.top(), rect.bottom() - self.height() - 8),
        )

    def eventFilter(self, watched, event):
        if (
            (watched is self.parent() or watched is self._anchor)
            and event.type()
            in {
                QEvent.Type.Resize,
                QEvent.Type.Move,
                QEvent.Type.Show,
            }
            and self.isVisible()
        ):
            self._reposition()
        return super().eventFilter(watched, event)
