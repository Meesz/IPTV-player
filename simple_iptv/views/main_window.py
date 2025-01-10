from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QPushButton, QListWidget, QSlider, QComboBox,
                            QTabWidget, QLabel, QLineEdit, QToolBar,
                            QWidgetAction, QFrame, QScrollArea,
                            QSplitter)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from .player_widget import PlayerWidget
from .notification import NotificationWidget, NotificationType
from utils.themes import Themes

class SearchBar(QLineEdit):
    def __init__(self):
        super().__init__()
        self.setPlaceholderText("🔍 Search channels...")
        self.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px 8px 36px;
                border-radius: 20px;
                min-width: 250px;
                background-color: #2d2d2d;
                border: 1px solid #404040;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #666666;
                background-color: #333333;
            }
            QLineEdit:hover {
                background-color: #333333;
            }
        """)

class EPGWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setFixedHeight(300)  # Fixed height for the entire EPG widget
        
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Create a scroll area for the content
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(5)
        
        # Current program
        self.current_title = QLabel("No program information")
        self.current_title.setStyleSheet("font-weight: bold;")
        self.current_title.setWordWrap(True)
        scroll_layout.addWidget(self.current_title)
        
        self.current_time = QLabel()
        scroll_layout.addWidget(self.current_time)
        
        self.description = QLabel()
        self.description.setWordWrap(True)
        scroll_layout.addWidget(self.description)
        
        # Upcoming programs
        scroll_layout.addWidget(QLabel("Upcoming:"))
        self.upcoming_list = QListWidget()
        scroll_layout.addWidget(self.upcoming_list)
        
        # Create scroll area and add the content
        scroll_area = QScrollArea()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Add scroll area to main layout
        layout.addWidget(scroll_area)
    
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
        
        # Create menu bar
        self._create_menu()
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create toolbar and search bar first
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setStyleSheet("""
            QToolBar {
                spacing: 10px;
                padding: 5px 15px;
                background: transparent;
            }
        """)
        self.addToolBar(self.toolbar)
        
        # Add search bar
        self.search_bar = SearchBar()
        self.toolbar.addWidget(self.search_bar)
        
        # Create splitter for resizable panels
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Create left sidebar
        self.left_panel = self._create_left_panel()
        self.left_panel.setMinimumWidth(200)  # Set minimum width for left panel
        
        # Create right panel with player
        right_panel = self._create_right_panel()
        right_panel.setMinimumWidth(400)  # Set minimum width for player
        
        # Add panels to splitter
        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(right_panel)
        
        # Set initial sizes (1:4 ratio)
        self.splitter.setSizes([200, 800])
        
        # Connect splitter moved signal
        self.splitter.splitterMoved.connect(self._handle_splitter_moved)
        
        # Add splitter to main layout
        main_layout.addWidget(self.splitter)
        
        # Create notification widget
        self.notification = NotificationWidget(self)
        
        # Apply dark theme
        self.setStyleSheet(Themes.get_dark_theme())
    
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
        file_menu = menubar.addMenu('&File')
        
        # Add Playlist Manager action
        self.playlist_manager_action = QAction('&Playlist Manager', self)
        self.playlist_manager_action.setShortcut('Ctrl+P')
        self.playlist_manager_action.setStatusTip('Open playlist manager')
        file_menu.addAction(self.playlist_manager_action)
        
        # Add separator
        file_menu.addSeparator()
        
        # Add Exit action
        exit_action = QAction('&Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Exit application')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # EPG menu
        epg_menu = menubar.addMenu('&EPG')
        
        # Add EPG actions
        self.load_epg_file_action = QAction('Load from &File...', self)
        self.load_epg_file_action.setStatusTip('Load EPG data from XML file')
        epg_menu.addAction(self.load_epg_file_action)
        
        # Add URL input
        self.epg_url_input = QLineEdit()
        self.epg_url_input.setPlaceholderText("Enter EPG URL...")
        self.load_epg_url_button = QPushButton("Load")
        
        url_widget = QWidget()
        url_layout = QHBoxLayout(url_widget)
        url_layout.setContentsMargins(8, 0, 8, 0)
        url_layout.addWidget(self.epg_url_input)
        url_layout.addWidget(self.load_epg_url_button)
        
        url_action = QWidgetAction(epg_menu)
        url_action.setDefaultWidget(url_widget)
        epg_menu.addAction(url_action)
    
    def _handle_splitter_moved(self, pos, index):
        """Handle splitter movement to show/hide search bar"""
        # Get the width of the left panel (sidebar)
        sizes = self.splitter.sizes()
        if not sizes:
            return
        
        left_panel_width = sizes[0]
        
        # Show/hide search bar based on sidebar width
        if left_panel_width < 50:  # Collapsed
            self.search_bar.hide()
            self.toolbar.hide()
        else:  # Expanded
            self.search_bar.show()
            self.toolbar.show()