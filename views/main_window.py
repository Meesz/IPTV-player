"""
This module contains the main window of the Simple IPTV Player application.
"""

# pylint: disable=no-name-in-module
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QToolBar,
    QSplitter,
    QPushButton,
)
from PyQt6.QtCore import Qt
from utils.themes import Themes
from utils.styles import ToolbarStyle
from views.notification import NotificationWidget, NotificationType
from views.search_bar import SearchBar
from views.left_panel import LeftPanel
from views.right_panel import RightPanel
from views.menu_bar import MenuBar
from playback.manager import PlaybackManager


class MainWindow(QMainWindow):
    """The main window of the Simple IPTV Player application."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple IPTV Player")
        self.setMinimumSize(1024, 768)

        # Initialize components
        self._init_ui()
        self._setup_toolbar()
        self.menu_bar = MenuBar(self)  # Store reference to menu bar
        self.setMenuBar(self.menu_bar)

        # Apply theme
        self.setStyleSheet(Themes.get_dark_theme())

        # Create notification widget
        self.notification = NotificationWidget(self)

        self.playback_manager = PlaybackManager(self)
        self.setup_playback_features()

        # Initialize player_controller to None - it will be set from main.py
        self.player_controller = None

    # Menu bar properties
    @property
    def playlist_manager_action(self):
        """Get the playlist manager action."""
        return self.menu_bar.playlist_manager_action

    @property
    def load_epg_file_action(self):
        """Get the load EPG file action."""
        return self.menu_bar.load_epg_file_action

    @property
    def epg_url_input(self):
        """Get the EPG URL input."""
        return self.menu_bar.epg_url_input

    @property
    def load_epg_url_button(self):
        """Get the load EPG URL button."""
        return self.menu_bar.load_epg_url_button

    # Add property getters for UI components
    @property
    def category_combo(self):
        """Get the category combo box."""
        return self.left_panel.category_combo

    @property
    def channel_list(self):
        """Get the channel list widget."""
        return self.left_panel.channel_list

    @property
    def favorites_list(self):
        """Get the favorites list widget."""
        return self.left_panel.favorites_list

    @property
    def play_button(self):
        """Get the play button."""
        return self.right_panel.play_button

    @property
    def stop_button(self):
        """Get the stop button."""
        return self.right_panel.stop_button

    @property
    def volume_slider(self):
        """Get the volume slider."""
        return self.right_panel.volume_slider

    @property
    def favorite_button(self):
        """Get the favorite button."""
        return self.right_panel.favorite_button

    @property
    def player_widget(self):
        """Get the player widget."""
        return self.right_panel.player_widget

    def _init_ui(self):
        """Initialize the main UI components."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create and setup splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.left_panel = LeftPanel()
        self.right_panel = RightPanel()

        self.left_panel.setMinimumWidth(200)
        self.right_panel.setMinimumWidth(400)

        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setSizes([200, 800])
        self.splitter.splitterMoved.connect(self._handle_splitter_moved)

        main_layout.addWidget(self.splitter)

    def _setup_toolbar(self):
        """Setup the toolbar with search functionality."""
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setStyleSheet(ToolbarStyle.TOOLBAR)

        self.search_bar = SearchBar()
        self.toolbar.addWidget(self.search_bar)

        self.addToolBar(self.toolbar)

    def _handle_splitter_moved(self):
        """Handle splitter movement to show/hide search bar."""
        sizes = self.splitter.sizes()
        if not sizes:
            return

        left_panel_width = sizes[0]
        if left_panel_width < 50:  # Collapsed
            self.search_bar.hide()
            self.toolbar.hide()
        else:  # Expanded
            self.search_bar.show()
            self.toolbar.show()

    def apply_theme(self, theme: str):
        """Apply the given theme to the main window."""
        self.setStyleSheet(theme)

    def show_notification(
        self, message: str, notification_type: NotificationType = NotificationType.INFO
    ):
        """Show a notification with the given message and type."""
        self.notification.show_message(message, notification_type)

    def setup_playback_features(self):
        # Add PiP button to player controls
        self.pip_btn = QPushButton("PiP Mode")
        self.pip_btn.clicked.connect(self.toggle_pip_mode)

        # Add to right panel's controls
        if hasattr(self.right_panel, "controls_layout"):
            self.right_panel.controls_layout.addWidget(self.pip_btn)
        else:
            # Fallback to adding directly to right panel's layout
            self.right_panel.layout().addWidget(self.pip_btn)

    def toggle_pip_mode(self):
        print("PiP button clicked")  # Debug
        if not self.playback_manager.pip_window:
            current_channel = self.get_current_channel()
            print(f"Current channel: {current_channel}")  # Debug
            if current_channel:
                print(
                    f"Starting PiP with: {current_channel.name}, {current_channel.url}"
                )  # Debug
                self.playback_manager.start_pip(
                    current_channel.name, current_channel.url
                )
        else:
            print("Stopping PiP")  # Debug
            self.playback_manager.stop_pip()

    def get_current_channel(self):
        """Get the currently selected channel"""
        # Get the currently playing channel from player controller
        if self.player_controller and self.player_controller.current_channel:
            print(
                f"Found current channel: {self.player_controller.current_channel.name}"
            )  # Debug
            return self.player_controller.current_channel

        print("No current channel found in player controller")  # Debug
        return None

