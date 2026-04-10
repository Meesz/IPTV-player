from PyQt6.QtCore import pyqtSignal
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
        self.textChanged.connect(self.search_changed.emit)
