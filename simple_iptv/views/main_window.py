from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QPushButton, QListWidget, QSlider, QComboBox,
                            QTabWidget, QLabel, QScrollArea, QFrame, QLineEdit,
                            QMenu, QWidgetAction)
from PyQt6.QtCore import Qt
from .player_widget import PlayerWidget

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
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)
        
        # Create left panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Add category selector
        self.category_combo = QComboBox()
        left_layout.addWidget(self.category_combo)
        
        # Add tabs for channels and favorites
        self.tabs = QTabWidget()
        self.channel_list = QListWidget()
        self.favorites_list = QListWidget()
        
        self.tabs.addTab(self.channel_list, "Channels")
        self.tabs.addTab(self.favorites_list, "Favorites")
        left_layout.addWidget(self.tabs)
        
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
        
        # Playback controls
        self.play_button = QPushButton("Play/Pause")
        self.stop_button = QPushButton("Stop")
        self.favorite_button = QPushButton("★")
        self.favorite_button.setCheckable(True)
        
        # Add all controls to layout
        controls_layout.addWidget(self.load_button)
        controls_layout.addWidget(self.load_epg_button)
        controls_layout.addWidget(self.play_button)
        controls_layout.addWidget(self.stop_button)
        controls_layout.addWidget(self.favorite_button)
        
        left_layout.addLayout(controls_layout)
        
        # Add volume control
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("Volume:"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        volume_layout.addWidget(self.volume_slider)
        left_layout.addLayout(volume_layout)
        
        # Add EPG widget
        self.epg_widget = EPGWidget()
        left_layout.addWidget(self.epg_widget)
        
        # Create right panel with player
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Add player widget
        self.player_widget = PlayerWidget()
        right_layout.addWidget(self.player_widget)
        
        # Add widgets to main layout
        layout.addWidget(left_panel, 1)
        layout.addWidget(right_panel, 4) 