from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QListWidgetItem,
    QHBoxLayout,
    QMainWindow,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.models import Channel, PlaylistReference
from ui.controllers.epg_controller import EPGController
from ui.controllers.favorites_controller import FavoritesController
from ui.controllers.main_controller import MainController
from ui.controllers.playlist_controller import PlaylistController
from ui.controllers.settings_controller import SettingsController
from ui.dialogs.playlist_manager_dialog import PlaylistManagerDialog
from ui.styles.styles import ToolbarStyle
from ui.styles.themes import Themes
from ui.widgets.left_panel import LeftPanel
from ui.widgets.menu_bar import MenuBar
from ui.widgets.notification import NotificationType, NotificationWidget
from ui.widgets.right_panel import RightPanel


class MainWindow(QMainWindow):
    def __init__(
        self,
        main_controller: MainController,
        playlist_controller: PlaylistController,
        epg_controller: EPGController,
        settings_controller: SettingsController,
        favorites_controller: FavoritesController,
    ):
        super().__init__()
        self.main_controller = main_controller
        self.playlist_controller = playlist_controller
        self.epg_controller = epg_controller
        self.settings_controller = settings_controller
        self.favorites_controller = favorites_controller
        self._current_channel: Channel | None = None

        self._apply_settings_to_window()
        self._init_ui()
        self._connect_signals()

        theme = self.settings_controller.get_setting("theme", "dark")
        self._theme = "dark" if theme == "dark" else "light"
        self.setStyleSheet(
            Themes.get_dark_theme() if self._theme == "dark" else Themes.get_light_theme()
        )
        self.main_controller.start()

    def _apply_settings_to_window(self) -> None:
        settings = self.settings_controller.settings
        self.setWindowTitle("Simple IPTV Player")
        self.resize(settings.window_width, settings.window_height)
        self.setMinimumSize(900, 560)
        self._theme = settings.theme

    def _init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.menu_bar = MenuBar(self)
        self.setMenuBar(self.menu_bar)
        self._setup_toolbar()

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.left_panel = LeftPanel()
        self.right_panel = RightPanel()
        self.right_panel.volume_slider.setValue(self.settings_controller.get_setting("volume", 100))
        self.right_panel.player_widget.set_volume(self.settings_controller.get_setting("volume", 100))

        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setSizes([320, 960])
        layout.addWidget(self.splitter)

        self.notification = NotificationWidget(self)

    def _setup_toolbar(self):
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setStyleSheet(ToolbarStyle.TOOLBAR)

        epg_widget = QWidget()
        epg_layout = QHBoxLayout(epg_widget)
        epg_layout.setContentsMargins(8, 0, 8, 0)
        epg_layout.addWidget(self.menu_bar.epg_url_input)
        epg_layout.addWidget(self.menu_bar.load_epg_url_button)
        self.toolbar.addWidget(epg_widget)
        self.addToolBar(self.toolbar)

    def _connect_signals(self):
        self.playlist_controller.playlist_loaded.connect(self._on_playlist_loaded)
        self.playlist_controller.error_occurred.connect(self._on_error)
        self.playlist_controller.loading_started.connect(self._on_playlist_loading_started)
        self.playlist_controller.loading_finished.connect(self._on_playlist_loading_finished)

        self.epg_controller.error_occurred.connect(self._on_error)
        self.epg_controller.epg_loaded.connect(self._on_epg_loaded)

        self.favorites_controller.changed.connect(self._refresh_favorites)
        self.favorites_controller.error_occurred.connect(self._on_error)

        self.menu_bar.playlist_manager_action.triggered.connect(
            self._open_playlist_manager
        )
        self.menu_bar.load_epg_file_action.triggered.connect(self._load_epg_file)
        self.menu_bar.load_epg_url_button.clicked.connect(self._load_epg_url)
        self.left_panel.category_combo.currentTextChanged.connect(
            self._on_category_changed
        )
        self.left_panel.channel_list.itemDoubleClicked.connect(self._on_channel_selected)
        self.left_panel.favorites_list.itemDoubleClicked.connect(
            self._on_channel_selected
        )
        self.left_panel.search_bar.search_changed.connect(self._on_search)

        self.right_panel.play_button.clicked.connect(self._on_play_button)
        self.right_panel.stop_button.clicked.connect(self.right_panel.player_widget.stop)
        self.right_panel.volume_slider.valueChanged.connect(self._on_volume_changed)
        self.right_panel.favorite_button.clicked.connect(self._on_toggle_favorite)

    def _on_playlist_loading_started(self):
        self.show_notification("Loading playlist...", NotificationType.INFO, duration=1200)

    def _on_playlist_loading_finished(self):
        self.right_panel.player_widget.stop()

    def _on_playlist_loaded(self, playlist):
        self.left_panel.category_combo.clear()
        self.left_panel.category_combo.addItem("All")
        self.left_panel.category_combo.addItems(playlist.categories)
        self.left_panel.add_channels(playlist.channels)
        self._refresh_favorites()

        self.settings_controller.save_settings(
            {
                "last_playlist_path": playlist.source_path,
                "last_playlist": playlist.source_path,
                "last_playlist_is_url": "true"
                if playlist.source_path.startswith("http")
                else "false",
            }
        )
        self.show_notification(
            f"Loaded {len(playlist.channels)} channels", NotificationType.SUCCESS
        )

    def _refresh_favorites(self):
        favorites = self.favorites_controller.get_favorites()
        self.left_panel.add_favorites(favorites)
        if self._current_channel:
            self._refresh_favorite_button()

    def _on_epg_loaded(self):
        self.show_notification("EPG data loaded", NotificationType.SUCCESS)

    def _on_channel_selected(self, item: QListWidgetItem):
        channel = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(channel, Channel):
            self._play_channel(channel)

    def _play_channel(self, channel: Channel):
        self._current_channel = channel
        self.right_panel.player_widget.play(channel.url)
        self._refresh_favorite_button()
        self.settings_controller.save_setting("last_channel_url", channel.url)
        self._update_epg(channel.epg_id)

    def _update_epg(self, channel_id: str):
        program = self.epg_controller.get_current_program(channel_id)
        self.left_panel.epg_widget.set_current_program(program)
        upcoming = self.epg_controller.get_upcoming_programs(channel_id)
        self.left_panel.epg_widget.set_upcoming_programs(upcoming)

    def _refresh_favorite_button(self):
        if not self._current_channel:
            self.right_panel.favorite_button.setEnabled(False)
            self.right_panel.favorite_button.setText("Favorite")
            return

        self.right_panel.favorite_button.setEnabled(True)
        is_favorite = self.favorites_controller.is_favorite(self._current_channel)
        self.right_panel.favorite_button.setText(
            "Unfavorite" if is_favorite else "Favorite"
        )

    def _on_play_button(self):
        if self._current_channel:
            self.right_panel.player_widget.play(self._current_channel.url)
        elif self.right_panel.player_widget.current_url:
            self.right_panel.player_widget.play(self.right_panel.player_widget.current_url)
        else:
            self.show_notification("No channel selected", NotificationType.WARNING)

    def _on_volume_changed(self, value: int):
        self.right_panel.player_widget.set_volume(value)
        self.settings_controller.save_setting("volume", value)

    def _on_toggle_favorite(self):
        if not self._current_channel:
            return
        changed = self.favorites_controller.toggle(self._current_channel)
        self._refresh_favorite_button()
        if changed:
            self.show_notification("Favorites updated", NotificationType.SUCCESS)

    def _on_category_changed(self, category: str):
        channels = self.playlist_controller.get_channels_by_category(category)
        self.left_panel.add_channels(channels)

    def _on_search(self, query: str):
        if not query:
            category = self.left_panel.category_combo.currentText() or "All"
            self._on_category_changed(category)
            return
        channels = self.playlist_controller.search_channels(query)
        self.left_panel.add_channels(channels)

    def _open_playlist_manager(self):
        dialog = PlaylistManagerDialog(self)
        dialog.set_playlists(self.playlist_controller.get_saved_playlists())
        dialog.playlist_selected.connect(self._on_playlist_selected_from_manager)
        if dialog.exec():
            self._save_playlists_from_dialog(dialog.get_playlists())

    def _save_playlists_from_dialog(self, playlists):
        self.playlist_controller.import_playlists(playlists)

    def _on_playlist_selected_from_manager(self, path: str, is_url: bool):
        loaded = self.playlist_controller.load_playlist(path, is_url)
        if loaded:
            self._save_playlist_reference(path, is_url, Path(path).name if not is_url else "URL Playlist")

    def _save_playlist_reference(self, path: str, is_url: bool, name: str):
        self.playlist_controller.save_playlist_reference(
            PlaylistReference(name=name, path=path, is_url=is_url)
        )

    def _load_epg_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open EPG File",
            "",
            "XMLTV Files (*.xml);;All Files (*)",
        )
        if path:
            self.epg_controller.load_epg_file(path)
            self.settings_controller.save_settings(
                {
                    "last_epg_path": path,
                    "epg_url": "",
                }
            )

    def _load_epg_url(self):
        url = self.menu_bar.epg_url_input.text().strip()
        if not url:
            self.show_notification("Enter an EPG URL", NotificationType.WARNING)
            return
        self.epg_controller.load_epg_url(url)
        self.settings_controller.save_settings({"epg_url": url, "last_epg_path": ""})

    def _on_error(self, message: str):
        self.show_notification(message, NotificationType.ERROR)

    def show_notification(self, message: str, type=NotificationType.INFO, duration: int = 3000):
        self.notification.show_message(message, type, duration=duration)

    def closeEvent(self, event):
        is_muted = (
            self.right_panel.player_widget.player.audio_get_mute()
            if getattr(self.right_panel.player_widget, "vlc_available", False)
            else False
        )
        self.settings_controller.save_settings(
            {
                "theme": self._theme,
                "window_width": self.width(),
                "window_height": self.height(),
                "is_muted": is_muted,
            }
        )
        super().closeEvent(event)
