from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QMainWindow,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.models import Channel, Playlist, PlaylistReference, Program
from ui.controllers.epg_controller import EPGController
from ui.controllers.favorites_controller import FavoritesController
from ui.controllers.history_controller import HistoryController
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
        history_controller: HistoryController,
    ):
        super().__init__()
        self.setObjectName("main_window")

        self.main_controller = main_controller
        self.playlist_controller = playlist_controller
        self.epg_controller = epg_controller
        self.settings_controller = settings_controller
        self.favorites_controller = favorites_controller
        self.history_controller = history_controller

        settings = self.settings_controller.settings
        self._theme = settings.theme
        self._current_channel: Channel | None = None
        self._active_playlist_path = settings.last_playlist_path
        self._pending_channel_url = settings.last_channel_url or ""
        self._pending_channel_group = settings.last_channel_group or ""

        self._apply_settings_to_window()
        self._init_ui()
        self._connect_signals()
        self._apply_theme()
        self._apply_saved_preferences()
        self._refresh_favorite_button()
        self._refresh_recent_channels()
        self.right_panel.set_source_context(self._active_playlist_path)
        self.main_controller.start()

    def _apply_settings_to_window(self) -> None:
        settings = self.settings_controller.settings
        self.setWindowTitle("Simple IPTV Player")
        self.resize(settings.window_width, settings.window_height)
        self.setMinimumSize(980, 640)
        self._theme = settings.theme

    def _init_ui(self) -> None:
        self.central_widget = QWidget()
        self.central_widget.setObjectName("content_shell")
        self.setCentralWidget(self.central_widget)

        layout = QVBoxLayout(self.central_widget)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(14)

        self.menu_bar = MenuBar(self)
        self.setMenuBar(self.menu_bar)
        self._setup_toolbar()

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        self.left_panel = LeftPanel()
        self.right_panel = RightPanel()
        volume = self.settings_controller.get_setting("volume", 100)
        self.right_panel.volume_slider.setValue(volume)
        self.right_panel.player_widget.set_volume(volume)

        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setSizes([390, 960])
        layout.addWidget(self.splitter, stretch=1)

        self.notification = NotificationWidget(self)

    def _setup_toolbar(self) -> None:
        self.toolbar = QToolBar()
        self.toolbar.setObjectName("main_toolbar")
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setStyleSheet(ToolbarStyle.TOOLBAR)

        epg_widget = QWidget()
        epg_layout = QHBoxLayout(epg_widget)
        epg_layout.setContentsMargins(0, 0, 0, 0)
        epg_layout.setSpacing(10)
        epg_layout.addWidget(self.menu_bar.epg_url_input, stretch=1)
        epg_layout.addWidget(self.menu_bar.load_epg_url_button)
        self.toolbar.addWidget(epg_widget)
        self.toolbar.addSeparator()

        self.playlist_status_label = QLabel("Playlist: none")
        self.playlist_status_label.setObjectName("playlist_status_chip")
        self.playlist_status_label.setProperty("stateTone", "default")
        self.epg_status_label = QLabel("EPG not loaded")
        self.epg_status_label.setObjectName("epg_status_chip")
        self.epg_status_label.setProperty("stateTone", "warning")

        self.toolbar.addWidget(self.playlist_status_label)
        self.toolbar.addWidget(self.epg_status_label)
        self.addToolBar(self.toolbar)

    def _connect_signals(self) -> None:
        self.playlist_controller.playlist_loaded.connect(self._on_playlist_loaded)
        self.playlist_controller.error_occurred.connect(self._on_error)
        self.playlist_controller.loading_started.connect(self._on_playlist_loading_started)
        self.playlist_controller.loading_finished.connect(self._on_playlist_loading_finished)

        self.epg_controller.error_occurred.connect(self._on_error)
        self.epg_controller.epg_loaded.connect(self._on_epg_loaded)

        self.favorites_controller.changed.connect(self._refresh_favorites)
        self.favorites_controller.error_occurred.connect(self._on_error)

        self.history_controller.changed.connect(self._refresh_recent_channels)
        self.history_controller.error_occurred.connect(self._on_error)

        self.menu_bar.playlist_manager_action.triggered.connect(self._open_playlist_manager)
        self.menu_bar.load_epg_file_action.triggered.connect(self._load_epg_file)
        self.menu_bar.load_epg_url_button.clicked.connect(self._load_epg_url)
        self.menu_bar.refresh_epg_action.triggered.connect(self._refresh_epg)
        self.menu_bar.play_on_single_click_action.toggled.connect(
            self._on_play_on_single_click_changed
        )
        self.menu_bar.show_now_playing_action.toggled.connect(
            self._on_show_now_playing_changed
        )

        self.left_panel.category_combo.currentTextChanged.connect(self._refresh_channel_list)
        self.left_panel.sort_combo.currentIndexChanged.connect(self._on_sort_mode_changed)
        self.left_panel.search_current_group_checkbox.toggled.connect(
            self._on_search_scope_changed
        )
        self.left_panel.channel_list.itemDoubleClicked.connect(self._on_channel_selected)
        self.left_panel.favorites_list.itemDoubleClicked.connect(self._on_channel_selected)
        self.left_panel.recent_list.itemDoubleClicked.connect(self._on_channel_selected)
        self.left_panel.channel_list.itemClicked.connect(self._on_channel_clicked)
        self.left_panel.favorites_list.itemClicked.connect(self._on_channel_clicked)
        self.left_panel.recent_list.itemClicked.connect(self._on_channel_clicked)
        self.left_panel.search_bar.search_changed.connect(self._refresh_channel_list)

        self.right_panel.play_button.clicked.connect(self._on_play_button)
        self.right_panel.stop_button.clicked.connect(self.right_panel.player_widget.stop)
        self.right_panel.volume_slider.valueChanged.connect(self._on_volume_changed)
        self.right_panel.favorite_button.clicked.connect(self._on_toggle_favorite)
        self.right_panel.player_widget.playback_state_changed.connect(
            self._on_playback_state_changed
        )

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            Themes.get_dark_theme() if self._theme == "dark" else Themes.get_light_theme()
        )

    def _apply_saved_preferences(self) -> None:
        settings = self.settings_controller.settings
        self.menu_bar.play_on_single_click_action.setChecked(settings.play_on_single_click)
        self.menu_bar.show_now_playing_action.setChecked(settings.show_now_playing_in_list)
        self.left_panel.search_current_group_checkbox.setChecked(
            settings.search_current_category_only
        )
        self.left_panel.set_sort_mode(settings.channel_sort_mode)
        self._update_epg_status_label()

    def _favorite_keys(self) -> set[tuple[str, str]]:
        return {channel.identity_key() for channel in self.favorites_controller.get_favorites()}

    def _current_channel_key(self) -> tuple[str, str] | None:
        if not self._current_channel:
            return None
        return self._current_channel.identity_key()

    def _current_programs_for_channels(self, channels: list[Channel]) -> dict[str, Program]:
        if not self.settings_controller.get_setting("show_now_playing_in_list", True):
            return {}
        programs: dict[str, Program] = {}
        for channel in channels:
            if not channel.epg_id:
                continue
            program = self.epg_controller.get_current_program(channel.epg_id)
            if program:
                programs[channel.epg_id] = program
        return programs

    def _current_playlist(self) -> Playlist | None:
        return self.playlist_controller.get_current_playlist()

    def _refresh_channel_list(self, *_args) -> None:
        playlist = self._current_playlist()
        if not playlist:
            self.left_panel.add_channels([], current_channel_key=self._current_channel_key())
            return

        channels = self._resolve_visible_channels(playlist)
        program_map = self._current_programs_for_channels(channels)
        self.left_panel.add_channels(
            channels,
            current_programs=program_map,
            show_now_playing=self.settings_controller.get_setting(
                "show_now_playing_in_list", True
            ),
            favorites=self._favorite_keys(),
            current_channel_key=self._current_channel_key(),
        )

    def _resolve_visible_channels(self, playlist: Playlist) -> list[Channel]:
        category = self.left_panel.category_combo.currentText() or "All"
        query = self.left_panel.search_bar.text().strip().lower()
        current_group_only = self.left_panel.search_current_group_checkbox.isChecked()

        if category == "All":
            channels = list(playlist.channels)
        else:
            channels = list(playlist.get_channels_by_category(category))

        if query:
            if not current_group_only:
                channels = list(playlist.channels)
            channels = [
                channel
                for channel in channels
                if query in channel.name.lower() or query in channel.group.lower()
            ]

        return self._sort_channels(channels)

    def _sort_channels(self, channels: list[Channel]) -> list[Channel]:
        sort_mode = self.left_panel.sort_combo.currentData() or "name_asc"
        favorites = self._favorite_keys()
        if sort_mode == "name_desc":
            return sorted(channels, key=lambda item: item.name.lower(), reverse=True)
        if sort_mode == "group":
            return sorted(channels, key=lambda item: (item.group.lower(), item.name.lower()))
        if sort_mode == "favorites_first":
            return sorted(
                channels,
                key=lambda item: (item.identity_key() not in favorites, item.name.lower()),
            )
        return sorted(channels, key=lambda item: item.name.lower())

    def _refresh_favorites(self) -> None:
        favorites = self.favorites_controller.get_favorites()
        program_map = self._current_programs_for_channels(favorites)
        self.left_panel.add_favorites(
            favorites,
            current_programs=program_map,
            show_now_playing=self.settings_controller.get_setting(
                "show_now_playing_in_list", True
            ),
            current_channel_key=self._current_channel_key(),
        )
        if self._current_channel:
            self._refresh_favorite_button()
        self._refresh_channel_list()

    def _refresh_recent_channels(self) -> None:
        recent = self.history_controller.get_recent_channels(limit=12)
        program_map = self._current_programs_for_channels(recent)
        self.left_panel.add_recent_channels(
            recent,
            current_programs=program_map,
            show_now_playing=self.settings_controller.get_setting(
                "show_now_playing_in_list", True
            ),
            favorites=self._favorite_keys(),
            current_channel_key=self._current_channel_key(),
        )

    def _on_playlist_loading_started(self) -> None:
        self.right_panel.player_widget.stop()
        self.right_panel.set_playback_state("connecting", "Loading playlist source")
        self.show_notification("Loading playlist...", NotificationType.INFO, duration=1200)

    def _on_playlist_loading_finished(self) -> None:
        return

    def _on_playlist_loaded(self, playlist: Playlist) -> None:
        self._active_playlist_path = playlist.source_path
        playlist_name = Path(playlist.source_path).name or playlist.source_path
        self._set_status_chip(
            self.playlist_status_label,
            f"Playlist: {playlist_name} ({len(playlist.channels)} ch)",
            "success",
        )

        self.left_panel.category_combo.blockSignals(True)
        self.left_panel.category_combo.clear()
        self.left_panel.category_combo.addItem("All")
        self.left_panel.category_combo.addItems(playlist.categories)
        target_group = self._pending_channel_group or self.settings_controller.get_setting(
            "last_channel_group", ""
        )
        if target_group and target_group in playlist.categories:
            self.left_panel.category_combo.setCurrentText(target_group)
        self.left_panel.category_combo.blockSignals(False)

        self._persist_playlist_state(playlist)
        self.right_panel.set_source_context(playlist.source_path)
        self._refresh_channel_list()
        self._refresh_favorites()
        self._refresh_recent_channels()
        self._restore_pending_channel(playlist)
        self.show_notification(
            f"Loaded {len(playlist.channels)} channels", NotificationType.SUCCESS
        )

    def _persist_playlist_state(self, playlist: Playlist) -> None:
        is_url = playlist.source_path.startswith(("http://", "https://"))
        self.settings_controller.save_settings(
            {
                "last_playlist_path": playlist.source_path,
                "last_playlist": playlist.source_path,
                "last_playlist_is_url": "true" if is_url else "false",
            }
        )

        existing_reference = self.playlist_controller.get_saved_playlist(playlist.source_path)
        if existing_reference:
            reference_name = existing_reference.name
        elif is_url:
            reference_name = "URL Playlist"
        else:
            reference_name = Path(playlist.source_path).name or "Playlist"

        self.playlist_controller.save_playlist_reference(
            PlaylistReference(
                name=reference_name,
                path=playlist.source_path,
                is_url=is_url,
            )
        )
        self.playlist_controller.update_playlist_metadata(
            playlist.source_path,
            channel_count=len(playlist.channels),
            last_loaded_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            last_status="ready",
            last_error="",
        )

    def _restore_pending_channel(self, playlist: Playlist) -> None:
        if not self._pending_channel_url:
            return
        channel = playlist.get_channel_by_url(self._pending_channel_url)
        if not channel:
            self._pending_channel_url = ""
            self._pending_channel_group = ""
            return
        self._pending_channel_url = ""
        self._pending_channel_group = ""
        self._play_channel(channel)

    def _on_epg_loaded(self) -> None:
        self._update_epg_status_label()
        self._refresh_channel_list()
        self._refresh_favorites()
        self._refresh_recent_channels()
        if self._current_channel:
            self._update_epg(self._current_channel.epg_id)
        self.show_notification(
            f"EPG loaded for {self.epg_controller.loaded_channel_count} channels",
            NotificationType.SUCCESS,
        )

    def _on_channel_clicked(self, item: QListWidgetItem) -> None:
        if self.settings_controller.get_setting("play_on_single_click", False):
            self._on_channel_selected(item)

    def _on_channel_selected(self, item: QListWidgetItem) -> None:
        channel = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(channel, Channel):
            return

        if channel.playlist_path and channel.playlist_path != self._active_playlist_path:
            self._pending_channel_url = channel.url
            self._pending_channel_group = channel.group
            is_url = channel.playlist_path.startswith(("http://", "https://"))
            self.playlist_controller.load_playlist(channel.playlist_path, is_url)
            return

        self._play_channel(channel)

    def _play_channel(self, channel: Channel) -> None:
        self._current_channel = channel
        self.left_panel.highlight_channel(channel)
        self.right_panel.player_widget.play(channel.url)
        self._refresh_favorite_button()
        self.settings_controller.save_settings(
            {
                "last_channel_url": channel.url,
                "last_channel_group": channel.group,
            }
        )
        if self._active_playlist_path:
            self.history_controller.record_channel(channel, self._active_playlist_path)
        self._update_epg(channel.epg_id)

    def _update_epg(self, channel_id: str) -> Program | None:
        program = self.epg_controller.get_current_program(channel_id)
        self.left_panel.epg_widget.set_current_program(program)
        upcoming = self.epg_controller.get_upcoming_programs(channel_id)
        self.left_panel.epg_widget.set_upcoming_programs(upcoming)
        self.right_panel.set_now_playing(self._current_channel, program, self._active_playlist_path)
        return program

    def _refresh_favorite_button(self) -> None:
        if not self._current_channel:
            self.right_panel.favorite_button.setEnabled(False)
            self.right_panel.favorite_button.setText("Favorite")
            return

        self.right_panel.favorite_button.setEnabled(True)
        is_favorite = self.favorites_controller.is_favorite(self._current_channel)
        self.right_panel.favorite_button.setText(
            "Unfavorite" if is_favorite else "Favorite"
        )

    def _on_play_button(self) -> None:
        if self._current_channel:
            self.right_panel.player_widget.play(self._current_channel.url)
            return
        if self.right_panel.player_widget.current_url:
            self.right_panel.player_widget.play(self.right_panel.player_widget.current_url)
            return
        self.show_notification("No channel selected", NotificationType.WARNING)

    def _on_volume_changed(self, value: int) -> None:
        self.right_panel.player_widget.set_volume(value)
        self.settings_controller.save_setting("volume", value)

    def _on_toggle_favorite(self) -> None:
        if not self._current_channel:
            return
        changed = self.favorites_controller.toggle(self._current_channel)
        self._refresh_favorite_button()
        if changed:
            self.show_notification("Favorites updated", NotificationType.SUCCESS)

    def _on_sort_mode_changed(self, *_args) -> None:
        self.settings_controller.save_setting(
            "channel_sort_mode", self.left_panel.sort_combo.currentData()
        )
        self._refresh_channel_list()

    def _on_search_scope_changed(self, checked: bool) -> None:
        self.settings_controller.save_setting("search_current_category_only", checked)
        self._refresh_channel_list()

    def _on_play_on_single_click_changed(self, checked: bool) -> None:
        self.settings_controller.save_setting("play_on_single_click", checked)

    def _on_show_now_playing_changed(self, checked: bool) -> None:
        self.settings_controller.save_setting("show_now_playing_in_list", checked)
        self._refresh_channel_list()
        self._refresh_favorites()
        self._refresh_recent_channels()

    def _on_playback_state_changed(self, state: str, detail: str) -> None:
        self.right_panel.set_playback_state(state, detail)

    def _open_playlist_manager(self) -> None:
        dialog = PlaylistManagerDialog(self)
        dialog.set_playlist_validator(self.playlist_controller.validate_playlist_reference)
        dialog.set_playlists(self.playlist_controller.get_saved_playlists())
        dialog.set_active_playlist(self._active_playlist_path)
        dialog.playlist_selected.connect(self._on_playlist_selected_from_manager)
        if dialog.exec():
            self._save_playlists_from_dialog(dialog.get_playlists())

    def _save_playlists_from_dialog(self, playlists: list[PlaylistReference]) -> None:
        self.playlist_controller.import_playlists(
            playlists,
            active_playlist_path=self._active_playlist_path,
        )

    def _on_playlist_selected_from_manager(self, path: str, is_url: bool) -> None:
        self.playlist_controller.load_playlist(path, is_url)

    def _load_epg_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open EPG File",
            "",
            "XMLTV Files (*.xml);;All Files (*)",
        )
        if not path:
            return
        if self.epg_controller.load_epg_file(path):
            loaded_at = datetime.now().strftime("%Y-%m-%d %H:%M")
            self.settings_controller.save_settings(
                {
                    "last_epg_path": path,
                    "epg_url": "",
                    "last_epg_loaded_at": loaded_at,
                }
            )
            self._update_epg_status_label()

    def _load_epg_url(self) -> None:
        url = self.menu_bar.epg_url_input.text().strip()
        if not url:
            self.show_notification("Enter an EPG URL", NotificationType.WARNING)
            return
        if self.epg_controller.load_epg_url(url):
            loaded_at = datetime.now().strftime("%Y-%m-%d %H:%M")
            self.settings_controller.save_settings(
                {
                    "epg_url": url,
                    "last_epg_path": "",
                    "last_epg_loaded_at": loaded_at,
                }
            )
            self._update_epg_status_label()

    def _refresh_epg(self) -> None:
        last_epg_path = self.settings_controller.get_setting("last_epg_path", "")
        last_epg_url = self.settings_controller.get_setting("last_epg_url", "")
        if last_epg_path:
            if self.epg_controller.load_epg_file(last_epg_path):
                self.settings_controller.save_setting(
                    "last_epg_loaded_at", datetime.now().strftime("%Y-%m-%d %H:%M")
                )
                self._update_epg_status_label()
            return
        if last_epg_url:
            if self.epg_controller.load_epg_url(last_epg_url):
                self.settings_controller.save_setting(
                    "last_epg_loaded_at", datetime.now().strftime("%Y-%m-%d %H:%M")
                )
                self._update_epg_status_label()
            return
        self.show_notification("No previous EPG source to refresh", NotificationType.WARNING)

    def _update_epg_status_label(self) -> None:
        loaded_at = self.settings_controller.get_setting("last_epg_loaded_at", "")
        if loaded_at:
            text = f"EPG: updated {loaded_at}"
            tone = "success"
        else:
            text = "EPG not loaded"
            tone = "warning"
        self._set_status_chip(self.epg_status_label, text, tone)
        self.left_panel.set_epg_status(text)

    @staticmethod
    def _set_status_chip(label: QLabel, text: str, tone: str) -> None:
        label.setText(text)
        label.setProperty("stateTone", tone)
        label.style().unpolish(label)
        label.style().polish(label)

    def _on_error(self, message: str) -> None:
        self.show_notification(message, NotificationType.ERROR)

    def show_notification(
        self,
        message: str,
        type: NotificationType = NotificationType.INFO,
        duration: int = 3000,
    ) -> None:
        self.notification.show_message(message, type, duration=duration)

    def closeEvent(self, event) -> None:
        is_muted = (
            self.right_panel.player_widget.player.audio_get_mute()
            if getattr(self.right_panel.player_widget, "vlc_available", False)
            and self.right_panel.player_widget.player is not None
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
