from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QLineEdit

from ui.styles.styles import SearchBarStyle


class SearchBar(QLineEdit):
    """Custom search bar widget with modern styling."""

    search_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("channel_search_bar")
        self.setPlaceholderText("Search channels or groups")
        self.setClearButtonEnabled(True)
        self.setStyleSheet(SearchBarStyle.SEARCH_BAR)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(lambda: self.search_changed.emit(self.text()))
        self.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self, _value: str) -> None:
        self._search_timer.start()
