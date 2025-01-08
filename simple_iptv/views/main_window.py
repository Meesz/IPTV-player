from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QPushButton, QListWidget, QSlider, QComboBox,
                            QTabWidget, QLabel, QLineEdit, QMenu, QToolBar,
                            QWidgetAction, QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QAction
from .player_widget import PlayerWidget
from .notification import NotificationWidget, NotificationType
from utils.themes import Themes

class SearchBar(QLineEdit):
    def __init__(self):
        super().__init__()
        self.setPlaceholderText("Search channels...")
        self.setStyleSheet("""
            QLineEdit {
                padding: 5px 10px;
                border-radius: 15px;
                min-width: 200px;
            }
        """)

class EPGWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        
        layout = QVBoxLayout(self)
        
        # Current program
        self.current_title = QLabel("No program information")
        self.current_title.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.current_title)
        
        self.current_time = QLabel()
        layout.addWidget(self.current_time)
        
        self.description = QLabel()
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        
        # Upcoming programs
        layout.addWidget(QLabel("Upcoming:"))
        self.upcoming_list = QListWidget()
        layout.addWidget(self.upcoming_list)
        
    def update_current_program(self, title: str, time_str: str, description: str):
        self.current_title.setText(title)
        self.current_time.setText(time_str)
        self.description.setText(description)
        
    def set_upcoming_programs(self, programs: list):
        self.upcoming_list.clear()
        for prog in programs:
            time_str = prog.start_time.strftime("%H:%M")
            self.upcoming_list.addItem(f"{time_str} - {prog.title}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple IPTV Player")
        self.setMinimumSize(1024, 768)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create toolbar
        self._create_toolbar()
        
        # Create content area
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addLayout(content_layout)
        
        # Create left sidebar
        left_panel = self._create_left_panel()
        content_layout.addWidget(left_panel)
        
        # Create right panel with player
        right_panel = self._create_right_panel()
        content_layout.addWidget(right_panel)
        
        # Set content stretch
        content_layout.setStretch(0, 1)  # Left panel
        content_layout.setStretch(1, 4)  # Right panel
        
        # Create notification widget
        self.notification = NotificationWidget(self)
        
        # Apply default theme
        self.apply_theme(Themes.get_dark_theme())
    
    def _create_toolbar(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        self.addToolBar(toolbar)
        
        # Add search bar
        self.search_bar = SearchBar()
        toolbar.addWidget(self.search_bar)
        
        # Add spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        
        # Add settings button
        self.settings_button = QPushButton("⚙")
        self.settings_button.setFixedSize(32, 32)
        self.settings_menu = QMenu(self.settings_button)
        
        # Add theme actions
        theme_menu = self.settings_menu.addMenu("Theme")
        self.light_theme_action = theme_menu.addAction("Light")
        self.dark_theme_action = theme_menu.addAction("Dark")
        
        self.settings_button.setMenu(self.settings_menu)
        toolbar.addWidget(self.settings_button)
    
    def _create_left_panel(self):
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        layout = QVBoxLayout(panel)
        
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
        
        # Add controls
        controls_layout = QHBoxLayout()
        
        # Playlist and EPG controls
        self.load_button = QPushButton("Load Playlist")
        self.load_epg_button = QPushButton("Load EPG")
        self.load_epg_menu = QMenu(self.load_epg_button)
        self.load_epg_button.setMenu(self.load_epg_menu)
        
        # Add menu actions
        self.load_epg_file_action = self.load_epg_menu.addAction("From File...")
        self.load_epg_menu.addSeparator()
        
        # Add URL input
        url_widget = QWidget()
        url_layout = QHBoxLayout(url_widget)
        url_layout.setContentsMargins(8, 0, 8, 0)
        
        self.epg_url_input = QLineEdit()
        self.epg_url_input.setPlaceholderText("Enter EPG URL...")
        url_layout.addWidget(self.epg_url_input)
        
        self.load_epg_url_button = QPushButton("Load")
        url_layout.addWidget(self.load_epg_url_button)
        
        # Add URL widget to menu
        url_action = QWidgetAction(self.load_epg_menu)
        url_action.setDefaultWidget(url_widget)
        self.load_epg_menu.addAction(url_action)
        
        # Add controls to layout
        controls_layout.addWidget(self.load_button)
        controls_layout.addWidget(self.load_epg_button)
        
        layout.addLayout(controls_layout)
        
        # Add EPG widget
        self.epg_widget = EPGWidget()
        layout.addWidget(self.epg_widget)
        
        return panel
    
    def _create_right_panel(self):
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        layout = QVBoxLayout(panel)
        
        # Add player widget
        self.player_widget = PlayerWidget()
        layout.addWidget(self.player_widget)
        
        # Add playback controls
        controls_layout = QHBoxLayout()
        
        self.play_button = QPushButton("Play/Pause")
        self.stop_button = QPushButton("Stop")
        self.favorite_button = QPushButton("★")
        self.favorite_button.setCheckable(True)
        
        controls_layout.addWidget(self.play_button)
        controls_layout.addWidget(self.stop_button)
        controls_layout.addWidget(self.favorite_button)
        
        # Add volume control
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("Volume:"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        volume_layout.addWidget(self.volume_slider)
        
        # Add controls to layout
        layout.addLayout(controls_layout)
        layout.addLayout(volume_layout)
        
        return panel
    
    def apply_theme(self, theme: str):
        self.setStyleSheet(theme)
    
    def show_notification(self, message: str, type: NotificationType = NotificationType.INFO):
        self.notification.show_message(message, type) 
    
    def _create_menu(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        # Add Playlist Manager action
        playlist_manager_action = QAction('Playlist Manager', self)
        playlist_manager_action.setShortcut('Ctrl+P')
        file_menu.addAction(playlist_manager_action)
        
        # Store the action for connecting signals
        self.playlist_manager_action = playlist_manager_action 