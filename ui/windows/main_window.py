from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
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
        is_muted = self.settings_controller.get_setting("is_muted", False)
        self.right_panel.volume_slider.setValue(volume)
        self.right_panel.player_widget.set_volume(volume)
        self.right_panel.player_widget.set_muted(is_muted)
        self.right_panel.mute_button.setText("Unmute" if is_muted else "Mute")

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
        self.playlist_controller.loading_progress.connect(self._on_playlist_loading_progress)
        self.playlist_controller.loading_cancelled.connect(self._on_playlist_loading_cancelled)
        self.playlist_controller.loading_finished.connect(self._on_playlist_loading_finished)

        self.epg_controller.error_occurred.connect(self._on_error)
        self.epg_controller.epg_loaded.connect(self._on_epg_loaded)
        self.epg_controller.loading_started.connect(self._on_epg_loading_started)
        self.epg_controller.loading_progress.connect(self._on_epg_loading_progress)
        self.epg_controller.loading_cancelled.connect(self._on_epg_loading_cancelled)
        self.epg_controller.loading_finished.connect(self._on_epg_loading_finished)

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
        self.menu_bar.show_library_panel_action.toggled.connect(
            self._on_left_panel_visibility_changed
        )

        self.left_panel.category_combo.currentTextChanged.connect(self._refresh_channel_list)
        self.left_panel.category_combo.currentTextChanged.connect(self._on_category_changed)
        self.left_panel.sort_combo.currentIndexChanged.connect(self._on_sort_mode_changed)
        self.left_panel.search_current_group_checkbox.toggled.connect(
            self._on_search_scope_changed
        )
        self.left_panel.tabs.currentChanged.connect(self._on_active_tab_changed)
        self.left_panel.channel_list.itemDoubleClicked.connect(self._on_channel_selected)
        self.left_panel.favorites_list.itemDoubleClicked.connect(self._on_channel_selected)
        self.left_panel.recent_list.itemDoubleClicked.connect(self._on_channel_selected)
        self.left_panel.channel_list.itemClicked.connect(self._on_channel_clicked)
        self.left_panel.favorites_list.itemClicked.connect(self._on_channel_clicked)
        self.left_panel.recent_list.itemClicked.connect(self._on_channel_clicked)
        self.left_panel.search_bar.search_changed.connect(self._refresh_channel_list)
        self.left_panel.search_bar.search_changed.connect(self._on_search_text_changed)
        self.splitter.splitterMoved.connect(self._on_splitter_moved)

        self.right_panel.play_button.clicked.connect(self._on_play_button)
        self.right_panel.stop_button.clicked.connect(self.right_panel.player_widget.stop)
        self.right_panel.retry_button.clicked.connect(self._on_retry_now)
        self.right_panel.mute_button.clicked.connect(self._on_toggle_mute)
        self.right_panel.copy_url_button.clicked.connect(self._on_copy_stream_url)
        self.right_panel.fullscreen_button.clicked.connect(self._on_toggle_fullscreen)
        self.right_panel.info_button.clicked.connect(self._on_channel_info)
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
        self.menu_bar.show_library_panel_action.setChecked(settings.left_panel_visible)
        self.left_panel.search_current_group_checkbox.setChecked(
            settings.search_current_category_only
        )
        self.left_panel.set_sort_mode(settings.channel_sort_mode)
        self.left_panel.tabs.setCurrentIndex(settings.active_tab_index)
        self.left_panel.search_bar.setText(settings.search_text)
        self.menu_bar.epg_url_input.setText(settings.last_epg_url)
        self.splitter.setSizes(list(settings.splitter_sizes))
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
            self.left_panel.show_loading_state(
                "channels",
                "No playlist loaded",
                "Add or select a playlist to browse channels.",
            )
            return

        channels = self.playlist_controller.search_channels(
            self.left_panel.search_bar.text(),
            category=self.left_panel.category_combo.currentText() or "All",
            current_category_only=self.left_panel.search_current_group_checkbox.isChecked(),
            sort_mode=self.left_panel.sort_combo.currentData() or "name_asc",
            favorite_keys=self._favorite_keys(),
        )
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
        self.left_panel.show_loading_state(
            "channels",
            "Loading playlist",
            "Fetching channels and validating the source. Results will appear here once parsing finishes.",
        )
        self.show_notification("Loading playlist...", NotificationType.INFO, duration=1200)
        self._set_status_chip(self.playlist_status_label, "Playlist: loading...", "warning")

    def _on_playlist_loading_progress(self, message: str) -> None:
        self.right_panel.set_playback_state("connecting", message)
        self.left_panel.show_loading_state("channels", "Loading playlist", message)
        self._set_status_chip(self.playlist_status_label, f"Playlist: {message}", "warning")

    def _on_playlist_loading_cancelled(self) -> None:
        self._set_status_chip(self.playlist_status_label, "Playlist: load cancelled", "warning")
        self.left_panel.show_loading_state(
            "channels",
            "Playlist load cancelled",
            "Select a playlist source to try again.",
        )

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
        target_group = (
            self._pending_channel_group
            or self.settings_controller.get_setting("selected_category", "All")
            or self.settings_controller.get_setting("last_channel_group", "")
        )
        if target_group and target_group in playlist.categories:
            self.left_panel.category_combo.setCurrentText(target_group)
        else:
            self.left_panel.category_combo.setCurrentText("All")
        self.left_panel.category_combo.blockSignals(False)
        self.settings_controller.save_setting(
            "selected_category", self.left_panel.category_combo.currentText() or "All"
        )

        self._persist_playlist_state(playlist)
        self.right_panel.set_source_context(playlist.source_path)
        self._refresh_channel_list()
        self._refresh_favorites()
        self._refresh_recent_channels()
        self._restore_pending_channel(playlist)
        warning_count = len(playlist.parse_warnings)
        if warning_count:
            self.show_notification(
                f"Loaded {len(playlist.channels)} channels with {warning_count} warnings",
                NotificationType.WARNING,
            )
        else:
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
            last_status="warning" if playlist.parse_warnings else "ready",
            last_error=playlist.parse_warnings[0].message if playlist.parse_warnings else "",
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

    def _on_epg_loading_started(self) -> None:
        self._set_status_chip(self.epg_status_label, "EPG: loading...", "warning")
        self.left_panel.epg_widget.set_loading_state("Refreshing EPG source")

    def _on_epg_loading_progress(self, message: str) -> None:
        self._set_status_chip(self.epg_status_label, f"EPG: {message}", "warning")
        self.left_panel.set_epg_status(f"EPG: {message}")
        self.left_panel.epg_widget.set_loading_state(message)

    def _on_epg_loading_cancelled(self) -> None:
        self._set_status_chip(self.epg_status_label, "EPG: load cancelled", "warning")
        self.left_panel.set_epg_status("EPG: load cancelled")
        self.left_panel.epg_widget.set_empty_state(
            "EPG refresh cancelled",
            "The previous guide data remains unchanged.",
        )

    def _on_epg_loading_finished(self) -> None:
        return

    def _on_epg_loaded(self) -> None:
        loaded_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        if self.epg_controller.last_loaded_is_url:
            self.settings_controller.save_settings(
                {
                    "epg_url": self.epg_controller.last_loaded_source,
                    "last_epg_path": "",
                    "last_epg_loaded_at": loaded_at,
                }
            )
        else:
            self.settings_controller.save_settings(
                {
                    "last_epg_path": self.epg_controller.last_loaded_source,
                    "epg_url": "",
                    "last_epg_loaded_at": loaded_at,
                }
            )
        self._update_epg_status_label()
        self._refresh_channel_list()
        self._refresh_favorites()
        self._refresh_recent_channels()
        if self._current_channel:
            self._update_epg(self._current_channel.epg_id)
        else:
            self.left_panel.epg_widget.set_empty_state(
                "Guide data ready",
                "Select a channel to see live and upcoming programming.",
            )
        warning_count = len(self.epg_controller.last_warnings)
        source_type = "URL" if self.epg_controller.last_loaded_is_url else "File"
        self.left_panel.set_epg_status(
            f"EPG: {source_type} / {self.epg_controller.loaded_channel_count} channels / {loaded_at}"
        )
        if warning_count:
            self.show_notification(
                f"EPG loaded for {self.epg_controller.loaded_channel_count} channels with {warning_count} warnings",
                NotificationType.WARNING,
            )
        else:
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
        self.right_panel.set_stream_url(channel.url)
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

    def _on_toggle_mute(self) -> None:
        muted = self.right_panel.player_widget.toggle_mute()
        self.right_panel.mute_button.setText("Unmute" if muted else "Mute")
        self.settings_controller.save_setting("is_muted", muted)

    def _on_retry_now(self) -> None:
        if self.right_panel.player_widget.retry_now():
            self.show_notification("Retrying current stream", NotificationType.INFO, duration=1500)
            return
        self.show_notification("No stream available to retry", NotificationType.WARNING)

    def _on_copy_stream_url(self) -> None:
        url = self.right_panel.current_stream_url or self.right_panel.player_widget.current_url or ""
        if not url:
            self.show_notification("No stream URL available", NotificationType.WARNING)
            return
        QApplication.clipboard().setText(url)
        self.show_notification("Stream URL copied", NotificationType.SUCCESS, duration=1500)

    def _on_toggle_fullscreen(self) -> None:
        if not self.right_panel.player_widget.toggle_fullscreen():
            self.show_notification("Start playback before entering fullscreen", NotificationType.WARNING)

    def _on_channel_info(self) -> None:
        if not self._current_channel:
            self.show_notification("No channel selected", NotificationType.WARNING)
            return
        channel = self._current_channel
        message = "\n".join(
            [
                f"Name: {channel.name}",
                f"Group: {channel.group or 'Uncategorized'}",
                f"Playlist: {channel.playlist_path or self._active_playlist_path or 'Current source'}",
                f"URL: {channel.url}",
                f"EPG ID: {channel.epg_id or 'Not set'}",
            ]
        )
        QMessageBox.information(self, "Channel Info", message)

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

    def _on_category_changed(self, category: str) -> None:
        self.settings_controller.save_setting("selected_category", category or "All")

    def _on_search_text_changed(self, value: str) -> None:
        self.settings_controller.save_setting("search_text", value)

    def _on_search_scope_changed(self, checked: bool) -> None:
        self.settings_controller.save_setting("search_current_category_only", checked)
        self._refresh_channel_list()

    def _on_active_tab_changed(self, index: int) -> None:
        self.settings_controller.save_setting("active_tab_index", index)

    def _on_splitter_moved(self, *_args) -> None:
        sizes = tuple(self.splitter.sizes())
        if len(sizes) == 2:
            self.settings_controller.save_setting("splitter_sizes", sizes)

    def _on_left_panel_visibility_changed(self, visible: bool) -> None:
        self.left_panel.setVisible(visible)
        self.settings_controller.save_setting("left_panel_visible", visible)
        if visible:
            self.splitter.setSizes(list(self.settings_controller.settings.splitter_sizes))

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
        dialog.set_playlist_validator(self.playlist_controller.validate_playlist_reference_detailed)
        dialog.set_playlist_tester(self.playlist_controller.test_playlist_reference)
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
            "XMLTV Files (*.xml *.xml.gz *.gz);;All Files (*)",
        )
        if not path:
            return
        self.epg_controller.load_epg_file(path)

    def _load_epg_url(self) -> None:
        url = self.menu_bar.epg_url_input.text().strip()
        if not url:
            self.show_notification("Enter an EPG URL", NotificationType.WARNING)
            return
        self.epg_controller.load_epg_url(url)

    def _refresh_epg(self) -> None:
        last_epg_path = self.settings_controller.get_setting("last_epg_path", "")
        last_epg_url = self.settings_controller.get_setting("last_epg_url", "")
        if last_epg_path:
            self.epg_controller.load_epg_file(last_epg_path)
            return
        if last_epg_url:
            self.epg_controller.load_epg_url(last_epg_url)
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
                "splitter_sizes": tuple(self.splitter.sizes()),
                "active_tab_index": self.left_panel.tabs.currentIndex(),
                "selected_category": self.left_panel.category_combo.currentText() or "All",
                "search_text": self.left_panel.search_bar.text(),
                "left_panel_visible": self.left_panel.isVisible(),
            }
        )
        super().closeEvent(event)
