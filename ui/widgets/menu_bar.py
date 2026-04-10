from PyQt6.QtWidgets import (
    QMenuBar,
    QLineEdit,
    QPushButton,
)
from PyQt6.QtGui import QAction

class MenuBar(QMenuBar):
    """The main menu bar for the application."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("app_menu_bar")
        self._init_file_menu()
        self._init_epg_menu()
        self._init_view_menu()

    def _init_file_menu(self):
        file_menu = self.addMenu("&File")

        self.playlist_manager_action = QAction("&Playlist Manager", self)
        self.playlist_manager_action.setShortcut("Ctrl+P")
        file_menu.addAction(self.playlist_manager_action)

        file_menu.addSeparator()

        exit_action = QAction("&Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(lambda: self.parent().close() if self.parent() else None)
        file_menu.addAction(exit_action)

    def _init_epg_menu(self):
        epg_menu = self.addMenu("&EPG")

        self.load_epg_file_action = QAction("Load from &File...", self)
        epg_menu.addAction(self.load_epg_file_action)

        self.refresh_epg_action = QAction("&Refresh Last Source", self)
        self.refresh_epg_action.setShortcut("Ctrl+R")
        epg_menu.addAction(self.refresh_epg_action)

        self.epg_url_input = QLineEdit()
        self.epg_url_input.setObjectName("epg_url_input")
        self.epg_url_input.setPlaceholderText("Enter EPG URL...")
        self.load_epg_url_button = QPushButton("Load")
        self.load_epg_url_button.setProperty("accent", True)

    def _init_view_menu(self):
        view_menu = self.addMenu("&View")

        self.play_on_single_click_action = QAction("Play on Single Click", self)
        self.play_on_single_click_action.setCheckable(True)
        view_menu.addAction(self.play_on_single_click_action)

        self.show_now_playing_action = QAction("Show Current Program in Lists", self)
        self.show_now_playing_action.setCheckable(True)
        view_menu.addAction(self.show_now_playing_action)
