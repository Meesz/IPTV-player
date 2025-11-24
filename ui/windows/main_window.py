from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QToolBar,
    QSplitter,
    QMessageBox,
    QFileDialog,
    QListWidgetItem,
)
from PyQt6.QtCore import Qt
from ui.widgets.left_panel import LeftPanel
from ui.widgets.right_panel import RightPanel
from ui.widgets.menu_bar import MenuBar
from ui.widgets.notification import NotificationWidget, NotificationType
from ui.widgets.search_bar import SearchBar
from ui.dialogs.playlist_manager_dialog import PlaylistManagerDialog
from ui.styles.themes import Themes
from ui.styles.styles import ToolbarStyle
from ui.controllers.main_controller import MainController
from ui.controllers.playlist_controller import PlaylistController
from ui.controllers.epg_controller import EPGController
from ui.controllers.settings_controller import SettingsController

class MainWindow(QMainWindow):
    def __init__(self, 
                 main_controller: MainController,
                 playlist_controller: PlaylistController,
                 epg_controller: EPGController,
                 settings_controller: SettingsController):
        super().__init__()
        self.main_controller = main_controller
        self.playlist_controller = playlist_controller
        self.epg_controller = epg_controller
        self.settings_controller = settings_controller

        self.setWindowTitle("Simple IPTV Player")
        self.setMinimumSize(1280, 720)

        self._init_ui()
        self._connect_signals()
        
        # Apply theme
        theme = self.settings_controller.get_setting("theme", "dark")
        if theme == "dark":
            self.setStyleSheet(Themes.get_dark_theme())
        else:
            self.setStyleSheet(Themes.get_light_theme())
            
        # Start application logic
        self.main_controller.start()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.menu_bar = MenuBar(self)
        self.setMenuBar(self.menu_bar)

        self._setup_toolbar()

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.left_panel = LeftPanel()
        self.right_panel = RightPanel()

        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setSizes([300, 980])
        
        main_layout.addWidget(self.splitter)

        self.notification = NotificationWidget(self)

    def _setup_toolbar(self):
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setStyleSheet(ToolbarStyle.TOOLBAR)

        # We can use the search bar from the left panel or create a new one.
        # The original design had a search bar in the toolbar.
        # But LeftPanel also has one. Let's use the one in LeftPanel for now, 
        # or if we want it in the toolbar, we should hide the one in LeftPanel.
        # The requirement says `ui/widgets/search_bar.py`.
        # Let's keep the toolbar search bar as the primary one.
        self.search_bar = SearchBar()
        self.toolbar.addWidget(self.search_bar)
        
        self.toolbar.addSeparator()
        
        epg_widget = QWidget()
        epg_layout = QHBoxLayout(epg_widget)
        epg_layout.setContentsMargins(8, 0, 8, 0)
        epg_layout.addWidget(self.menu_bar.epg_url_input)
        epg_layout.addWidget(self.menu_bar.load_epg_url_button)
        self.toolbar.addWidget(epg_widget)

        self.addToolBar(self.toolbar)

    def _connect_signals(self):
        # Playlist signals
        self.playlist_controller.playlist_loaded.connect(self._on_playlist_loaded)
        self.playlist_controller.error_occurred.connect(self._on_error)

        # UI signals
        self.menu_bar.playlist_manager_action.triggered.connect(self._open_playlist_manager)
        self.menu_bar.load_epg_file_action.triggered.connect(self._load_epg_file)
        self.menu_bar.load_epg_url_button.clicked.connect(self._load_epg_url)
        
        self.left_panel.category_combo.currentTextChanged.connect(self._on_category_changed)
        self.left_panel.channel_list.itemDoubleClicked.connect(self._on_channel_selected)
        self.search_bar.search_changed.connect(self._on_search)
        
        # Player controls
        self.right_panel.play_button.clicked.connect(lambda: self.right_panel.player_widget.play(self.right_panel.player_widget.current_url) if self.right_panel.player_widget.current_url else None)
        self.right_panel.stop_button.clicked.connect(self.right_panel.player_widget.stop)
        self.right_panel.volume_slider.valueChanged.connect(self.right_panel.player_widget.set_volume)

    def _on_playlist_loaded(self, playlist):
        self.left_panel.category_combo.clear()
        self.left_panel.category_combo.addItem("All")
        self.left_panel.category_combo.addItems(playlist.categories)
        self._update_channel_list(playlist.channels)
        self.show_notification(f"Loaded {len(playlist.channels)} channels", NotificationType.SUCCESS)

    def _update_channel_list(self, channels):
        self.left_panel.channel_list.clear()
        for channel in channels:
            item = QListWidgetItem(channel.name)
            item.setData(Qt.ItemDataRole.UserRole, channel)
            self.left_panel.channel_list.addItem(item)

    def _on_category_changed(self, category):
        channels = self.playlist_controller.get_channels_by_category(category)
        self._update_channel_list(channels)

    def _on_channel_selected(self, item):
        channel = item.data(Qt.ItemDataRole.UserRole)
        if channel:
            self.right_panel.player_widget.play(channel.url)
            # Update EPG
            program = self.epg_controller.get_current_program(channel.epg_id)
            self.left_panel.epg_widget.set_current_program(program)
            upcoming = self.epg_controller.get_upcoming_programs(channel.epg_id)
            self.left_panel.epg_widget.set_upcoming_programs(upcoming)
        
    def _on_search(self, query):
        channels = self.playlist_controller.search_channels(query)
        self._update_channel_list(channels)

    def _open_playlist_manager(self):
        dialog = PlaylistManagerDialog(self)
        dialog.set_playlists(self.playlist_controller.get_saved_playlists())
        dialog.playlist_selected.connect(self._on_playlist_selected_from_manager)
        dialog.exec()

    def _on_playlist_selected_from_manager(self, path, is_url):
        self.playlist_controller.load_playlist(path, is_url)
        self.playlist_controller.save_playlist_ref(path, path, is_url) # Name?

    def _load_epg_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open EPG File", "", "XMLTV Files (*.xml)")
        if path:
            self.epg_controller.load_epg(path)

    def _load_epg_url(self):
        url = self.menu_bar.epg_url_input.text()
        if url:
            # EPG service needs to support URL loading
            pass

    def _on_error(self, message):
        self.show_notification(message, NotificationType.ERROR)

    def show_notification(self, message, type=NotificationType.INFO):
        self.notification.show_message(message, type)
