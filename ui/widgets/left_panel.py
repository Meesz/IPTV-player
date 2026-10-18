from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.models import Channel, Program
from ui.styles.themes import Themes
from ui.widgets.channel_list_view import ChannelListView
from ui.widgets.search_bar import SearchBar

SORT_OPTIONS = [
    ("A-Z", "name_asc"),
    ("Z-A", "name_desc"),
    ("Group", "group"),
    ("Favorites First", "favorites_first"),
]

_OPEN_MANAGER_LABEL = "Open Playlist Manager"
_EMPTY_CHANNELS_TITLE = "No channels match"
_EMPTY_CHANNELS_DETAIL = "Adjust the category or search filters to broaden the results."
_EMPTY_FAVORITES_TITLE = "No favorite channels"
_EMPTY_FAVORITES_DETAIL = "Use the Favorite control while watching a channel to pin it here."
_EMPTY_RECENT_TITLE = "Nothing played recently"
_EMPTY_RECENT_DETAIL = "Recently watched channels will appear here after playback starts."


class ChannelLogoProvider(QWidget):
    logo_loaded = pyqtSignal(str, object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self._manager.finished.connect(self._on_reply_finished)
        self._cache: dict[str, QPixmap] = {}
        self._inflight: dict[QNetworkReply, str] = {}
        self._theme_mode = "dark"

    def set_theme_mode(self, mode: str) -> None:
        self._theme_mode = mode
        self._cache.clear()

    def request_logo(self, source: str, fallback_text: str) -> QPixmap:
        if not source:
            return self._fallback_logo(fallback_text, self._theme_mode)

        cached = self._cache.get(source)
        if cached is not None:
            return cached

        if source.startswith(("http://", "https://")):
            if source not in self._inflight.values():
                reply = self._manager.get(QNetworkRequest(QUrl(source)))
                self._inflight[reply] = source
            fallback = self._fallback_logo(fallback_text, self._theme_mode)
            self._cache[source] = fallback
            return fallback

        path = Path(source).expanduser()
        if path.exists():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                scaled = self._scale_logo(pixmap)
                self._cache[source] = scaled
                return scaled

        fallback = self._fallback_logo(fallback_text, self._theme_mode)
        self._cache[source] = fallback
        return fallback

    def _on_reply_finished(self, reply: QNetworkReply) -> None:
        source = reply.url().toString()
        if reply.error() == QNetworkReply.NetworkError.NoError:
            payload = reply.readAll().data()
            pixmap = QPixmap()
            if pixmap.loadFromData(payload):
                scaled = self._scale_logo(pixmap)
                self._cache[source] = scaled
                self.logo_loaded.emit(source, scaled)
        self._inflight.pop(reply, None)
        reply.deleteLater()

    @staticmethod
    def _scale_logo(pixmap: QPixmap) -> QPixmap:
        return pixmap.scaled(
            42,
            42,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

    @staticmethod
    def _fallback_logo(text: str, mode: str = "dark") -> QPixmap:
        size = 42
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        seed = max(1, sum(ord(char) for char in text))
        hue = seed % 360
        background = QColor.fromHsl(hue, 130, 108)
        foreground = Themes.color(mode, "text")

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, size, size, 12, 12)
        painter.fillPath(path, background)
        painter.setPen(foreground)
        font = painter.font()
        font.setBold(True)
        font.setPointSize(14)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, (text[:1] or "?").upper())
        painter.end()
        return pixmap


class CollectionStateWidget(QFrame):
    """Calm, centred empty/loading state with an optional action button."""

    action_requested = pyqtSignal()

    def __init__(self, title: str, detail: str, action_label: str = ""):
        super().__init__()
        self.setObjectName("collection_state")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.addStretch(1)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("state_title")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.detail_label = QLabel(detail)
        self.detail_label.setObjectName("state_detail")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

        self.action_button = QPushButton()
        self.action_button.setProperty("accent", True)
        self.action_button.clicked.connect(self.action_requested)
        layout.addSpacing(4)
        layout.addWidget(self.action_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(2)
        self._set_action(action_label)

    def _set_action(self, action_label: str) -> None:
        self.action_button.setText(action_label)
        self.action_button.setVisible(bool(action_label))

    def set_content(self, title: str, detail: str, action_label: str = "") -> None:
        self.title_label.setText(title)
        self.detail_label.setText(detail)
        self._set_action(action_label)


class LeftPanel(QFrame):
    """Guide panel: channel/favorite/recent collections with search and filters."""

    manage_sources_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("library_panel")
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setMinimumWidth(340)
        self._logo_provider = ChannelLogoProvider(self)
        self._collection_views: dict[QWidget, tuple[QStackedWidget, CollectionStateWidget]] = {}
        self._channel_program_resolver: Callable[[list[Channel]], dict[str, Program]] | None = None
        self._channel_program_timer = QTimer(self)
        self._channel_program_timer.setSingleShot(True)
        self._channel_program_timer.timeout.connect(self._refresh_visible_channel_programs)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.tabs = QTabWidget()
        tab_bar = self.tabs.tabBar()
        tab_bar.setExpanding(True)
        tab_bar.setUsesScrollButtons(False)
        tab_bar.setElideMode(Qt.TextElideMode.ElideRight)
        tab_bar.setDrawBase(False)
        self.channel_list = ChannelListView(self._logo_provider)
        self.channel_list.visible_channels_changed.connect(self._schedule_visible_program_refresh)
        self.favorites_list = ChannelListView(self._logo_provider)
        self.recent_list = ChannelListView(self._logo_provider)

        self.tabs.addTab(self._build_channels_page(), "Channels")
        self.tabs.addTab(
            self._wrap_collection(self.favorites_list, _EMPTY_FAVORITES_TITLE, _EMPTY_FAVORITES_DETAIL),
            "Favorites",
        )
        self.tabs.addTab(
            self._wrap_collection(self.recent_list, _EMPTY_RECENT_TITLE, _EMPTY_RECENT_DETAIL),
            "Recent",
        )
        layout.addWidget(self.tabs, stretch=1)

    def _build_channels_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        self.search_bar = SearchBar()
        layout.addWidget(self.search_bar)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(8)

        self.category_combo = QComboBox()
        self.category_combo.setPlaceholderText("Category")
        controls.addWidget(self.category_combo, stretch=2)

        self.sort_combo = QComboBox()
        for label, value in SORT_OPTIONS:
            self.sort_combo.addItem(label, value)
        controls.addWidget(self.sort_combo, stretch=1)
        layout.addLayout(controls)

        self.search_current_group_checkbox = QCheckBox("Search within category")
        self.search_current_group_checkbox.setChecked(True)
        layout.addWidget(self.search_current_group_checkbox)

        layout.addWidget(
            self._wrap_collection(
                self.channel_list,
                "No playlist loaded",
                "Load a playlist to browse channels.",
                action_label=_OPEN_MANAGER_LABEL,
            ),
            stretch=1,
        )
        return page

    def _wrap_collection(
        self,
        widget: QWidget,
        title: str,
        detail: str,
        *,
        action_label: str = "",
    ) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        stacked = QStackedWidget()
        state = CollectionStateWidget(title, detail, action_label)
        state.action_requested.connect(self.manage_sources_requested)
        stacked.addWidget(widget)
        stacked.addWidget(state)
        layout.addWidget(stacked)
        self._collection_views[widget] = (stacked, state)
        stacked.setCurrentWidget(state)
        return container

    def focus_search(self) -> None:
        self.tabs.setCurrentIndex(0)
        self.search_bar.setFocus()

    def add_channels(
        self,
        channels: list[Channel],
        *,
        current_programs: dict[str, Program] | None = None,
        show_now_playing: bool = True,
        favorites: set[tuple[str, str]] | None = None,
        current_channel_key: tuple[str, str] | None = None,
    ) -> None:
        self.set_channel_results(
            channels,
            current_programs=current_programs,
            show_now_playing=show_now_playing,
            favorites=favorites,
            current_channel_key=current_channel_key,
            empty_title=_EMPTY_CHANNELS_TITLE,
            empty_detail=_EMPTY_CHANNELS_DETAIL,
        )

    def set_channel_results(  # noqa: PLR0913  (cohesive view-update options)
        self,
        channels: list[Channel],
        *,
        current_programs: dict[str, Program] | None = None,
        current_program_resolver: Callable[[list[Channel]], dict[str, Program]] | None = None,
        show_now_playing: bool = True,
        favorites: set[tuple[str, str]] | None = None,
        current_channel_key: tuple[str, str] | None = None,
        empty_title: str = _EMPTY_CHANNELS_TITLE,
        empty_detail: str = _EMPTY_CHANNELS_DETAIL,
        batch_size: int = 250,
        progress_callback: Callable[[int, int], None] | None = None,
        completion_callback: Callable[[], None] | None = None,
    ) -> None:
        self.cancel_channel_population()
        favorites = favorites or set()
        current_programs = current_programs or {}
        total = len(channels)

        if total == 0:
            self.channel_list.clear_channels()
            self._set_collection_state(self.channel_list, empty_title, empty_detail)
            if progress_callback:
                progress_callback(0, 0)
            if completion_callback:
                completion_callback()
            return

        self._show_collection(self.channel_list)
        self._channel_program_resolver = current_program_resolver if show_now_playing else None
        self.channel_list.set_channels(
            channels,
            favorite_keys=favorites,
            current_channel_key=current_channel_key,
            show_now_playing=show_now_playing,
        )
        self.channel_list.update_current_programs(current_programs)
        if current_channel_key:
            self.channel_list.select_channel_key(current_channel_key)
        self._schedule_visible_program_refresh()
        if progress_callback:
            progress_callback(total, total)
        if completion_callback:
            QTimer.singleShot(0, completion_callback)

    def cancel_channel_population(self) -> None:
        self._channel_program_resolver = None
        self._channel_program_timer.stop()
        self.channel_list.cancel_pending_updates()

    def add_favorites(
        self,
        channels: list[Channel],
        *,
        current_programs: dict[str, Program] | None = None,
        show_now_playing: bool = True,
        current_channel_key: tuple[str, str] | None = None,
    ) -> None:
        current_programs = current_programs or {}
        if not channels:
            self.favorites_list.clear_channels()
            self._set_collection_state(self.favorites_list, _EMPTY_FAVORITES_TITLE, _EMPTY_FAVORITES_DETAIL)
            return

        self._show_collection(self.favorites_list)
        favorites_set = {channel.identity_key() for channel in channels}
        meta_suffixes = {i: f"Source {Path(ch.playlist_path or 'active').name}" for i, ch in enumerate(channels)}
        self.favorites_list.set_channels(
            channels,
            favorite_keys=favorites_set,
            current_channel_key=current_channel_key,
            show_now_playing=show_now_playing,
            meta_suffixes=meta_suffixes,
        )
        self.favorites_list.update_current_programs(current_programs)
        if current_channel_key:
            self.favorites_list.select_channel_key(current_channel_key)

    def add_recent_channels(
        self,
        channels: list[Channel],
        *,
        current_programs: dict[str, Program] | None = None,
        show_now_playing: bool = True,
        favorites: set[tuple[str, str]] | None = None,
        current_channel_key: tuple[str, str] | None = None,
    ) -> None:
        current_programs = current_programs or {}
        if not channels:
            self.recent_list.clear_channels()
            self._set_collection_state(self.recent_list, _EMPTY_RECENT_TITLE, _EMPTY_RECENT_DETAIL)
            return

        self._show_collection(self.recent_list)
        meta_suffixes: dict[int, str] = {}
        for i, ch in enumerate(channels):
            if ch.last_played_at:
                played_at = datetime.fromtimestamp(ch.last_played_at).strftime("%Y-%m-%d %H:%M")
                meta_suffixes[i] = f"Last played {played_at}"
        self.recent_list.set_channels(
            channels,
            favorite_keys=favorites or set(),
            current_channel_key=current_channel_key,
            show_now_playing=show_now_playing,
            meta_suffixes=meta_suffixes,
        )
        self.recent_list.update_current_programs(current_programs)
        if current_channel_key:
            self.recent_list.select_channel_key(current_channel_key)

    def show_loading_state(self, target: str, title: str, detail: str, *, action_label: str = "") -> None:
        widget = self._widget_for_target(target)
        self._set_collection_state(widget, title, detail, action_label)

    def set_sort_mode(self, mode: str) -> None:
        index = self.sort_combo.findData(mode)
        if index >= 0:
            self.sort_combo.setCurrentIndex(index)

    def set_theme_mode(self, mode: str) -> None:
        self._logo_provider.set_theme_mode(mode)
        for view in (self.channel_list, self.favorites_list, self.recent_list):
            view.set_theme_mode(mode)

    def highlight_channel(self, channel: Channel) -> None:
        for view in (self.channel_list, self.favorites_list, self.recent_list):
            view.select_channel_key(channel.identity_key())

    def _widget_for_target(self, target: str) -> QWidget:
        mapping = {
            "channels": self.channel_list,
            "favorites": self.favorites_list,
            "recent": self.recent_list,
        }
        return mapping[target]

    def _set_collection_state(self, widget: QWidget, title: str, detail: str, action_label: str = "") -> None:
        stacked, state = self._collection_views[widget]
        state.set_content(title, detail, action_label)
        stacked.setCurrentWidget(state)

    def _show_collection(self, widget: QWidget) -> None:
        stacked, _ = self._collection_views[widget]
        stacked.setCurrentWidget(widget)

    def _schedule_visible_program_refresh(self) -> None:
        if self._channel_program_resolver is None:
            return
        self._channel_program_timer.start(75)

    def _refresh_visible_channel_programs(self) -> None:
        if self._channel_program_resolver is None:
            return
        visible_channels = self.channel_list.visible_channels()
        if not visible_channels:
            return
        programs = self._channel_program_resolver(visible_channels)
        self.channel_list.update_current_programs(programs)
