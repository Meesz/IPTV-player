from PyQt6.QtWidgets import QFrame, QVBoxLayout, QComboBox, QTabWidget, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt
from ui.widgets.epg_widget import EPGWidget
from ui.widgets.search_bar import SearchBar

class LeftPanel(QFrame):
    """A panel containing channel categories, lists, and EPG information."""

    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setFixedWidth(300)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Search Bar
        self.search_bar = SearchBar()
        layout.addWidget(self.search_bar)

        # Add category selector
        self.category_combo = QComboBox()
        layout.addWidget(self.category_combo)

        # Add tabs for channels and favorites
        self.tabs = QTabWidget()
        self.channel_list = QListWidget()
        self.favorites_list = QListWidget()

        self.tabs.addTab(self.channel_list, "Channels")
        self.tabs.addTab(self.favorites_list, "Favorites")
        layout.addWidget(self.tabs)

        # Add EPG widget
        self.epg_widget = EPGWidget()
        layout.addWidget(self.epg_widget)

    def clear_channels(self):
        self.channel_list.clear()
        self.favorites_list.clear()

    def add_channels(self, channels):
        self.channel_list.clear()
        for channel in channels:
            item = self._channel_item(channel.name, channel)
            self.channel_list.addItem(item)

    def add_favorites(self, channels):
        self.favorites_list.clear()
        for channel in channels:
            item = self._channel_item(channel.name, channel)
            self.favorites_list.addItem(item)

    @staticmethod
    def _channel_item(name, channel):
        item = QListWidgetItem(name)
        item.setData(Qt.ItemDataRole.UserRole, channel)
        return item
