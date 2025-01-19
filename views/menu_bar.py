"""
Module containing the MenuBar widget for the application.
"""

# pylint: disable=no-name-in-module
from PyQt6.QtWidgets import (
    QMenuBar,
    QWidget,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidgetAction,
)
from PyQt6.QtGui import QAction


class MenuBar(QMenuBar):
    """The main menu bar for the application."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_file_menu()
        self._init_epg_menu()

    def _init_file_menu(self):
        """Initialize the File menu."""
        file_menu = self.addMenu("&File")

        # Add Playlist Manager action
        self.playlist_manager_action = QAction("&Playlist Manager", self)
        self.playlist_manager_action.setShortcut("Ctrl+P")
        self.playlist_manager_action.setStatusTip("Open playlist manager")
        file_menu.addAction(self.playlist_manager_action)

        # Add separator
        file_menu.addSeparator()

        # Add Exit action
        exit_action = QAction("&Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Exit application")
        exit_action.triggered.connect(self.parent().close)
        file_menu.addAction(exit_action)

    def _init_epg_menu(self):
        """Initialize the EPG menu."""
        epg_menu = self.addMenu("&EPG")

        # Add EPG actions
        self.load_epg_file_action = QAction("Load from &File...", self)
        self.load_epg_file_action.setStatusTip("Load EPG data from XML file")
        epg_menu.addAction(self.load_epg_file_action)

        # Add URL input
        self.epg_url_input = QLineEdit()
        self.epg_url_input.setPlaceholderText("Enter EPG URL...")
        self.load_epg_url_button = QPushButton("Load")
        self.load_epg_url_button.clicked.connect(self._load_epg_from_url)
        
        url_widget = QWidget()
        url_layout = QHBoxLayout(url_widget)
        url_layout.setContentsMargins(8, 0, 8, 0)
        url_layout.addWidget(self.epg_url_input)
        url_layout.addWidget(self.load_epg_url_button)

        url_action = QWidgetAction(epg_menu)
        url_action.setDefaultWidget(url_widget)
        epg_menu.addAction(url_action)

    def _load_epg_from_url(self):
        """Load EPG data from the URL in the input field."""
        url = self.epg_url_input.text().strip()
        if url:
            # The EPG controller will be accessed through the main window
            self.parent().epg_controller.load_epg_from_url(url)
