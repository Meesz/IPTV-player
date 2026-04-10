from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.models import Channel, Program
from ui.widgets.epg_widget import EPGWidget
from ui.widgets.search_bar import SearchBar


SORT_OPTIONS = [
    ("A-Z", "name_asc"),
    ("Z-A", "name_desc"),
    ("Group", "group"),
    ("Favorites First", "favorites_first"),
]


class ChannelLogoProvider(QWidget):
    logo_loaded = pyqtSignal(str, object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self._manager.finished.connect(self._on_reply_finished)
        self._cache: dict[str, QPixmap] = {}
        self._inflight: dict[QNetworkReply, str] = {}

    def request_logo(self, source: str, fallback_text: str) -> QPixmap:
        if not source:
            return self._fallback_logo(fallback_text)

        cached = self._cache.get(source)
        if cached is not None:
            return cached

        if source.startswith(("http://", "https://")):
            if source not in self._inflight.values():
                reply = self._manager.get(QNetworkRequest(QUrl(source)))
                self._inflight[reply] = source
            fallback = self._fallback_logo(fallback_text)
            self._cache[source] = fallback
            return fallback

        path = Path(source).expanduser()
        if path.exists():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                scaled = self._scale_logo(pixmap)
                self._cache[source] = scaled
                return scaled

        fallback = self._fallback_logo(fallback_text)
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
    def _fallback_logo(text: str) -> QPixmap:
        size = 42
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        seed = max(1, sum(ord(char) for char in text))
        hue = seed % 360
        background = QColor.fromHsl(hue, 130, 108)
        foreground = QColor("#0a171d")

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


class ChannelBadge(QLabel):
    def __init__(self, text: str, tone: str):
        super().__init__(text)
        self.setObjectName("channel_badge")
        self.setProperty("badgeTone", tone)


class ChannelListItemWidget(QFrame):
    def __init__(
        self,
        channel: Channel,
        *,
        logo_provider: ChannelLogoProvider,
        title: str,
        subtitle: str,
        meta: str,
        badges: list[tuple[str, str]],
    ):
        super().__init__()
        self.setObjectName("channel_row")
        self._channel = channel
        self._logo_source = channel.logo
        self._logo_provider = logo_provider
        self._init_ui(title, subtitle, meta, badges)
        self._apply_logo(self._logo_provider.request_logo(channel.logo, channel.name))
        self._logo_provider.logo_loaded.connect(self._on_logo_loaded)

    def _init_ui(
        self,
        title: str,
        subtitle: str,
        meta: str,
        badges: list[tuple[str, str]],
    ) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        self.logo_label = QLabel()
        self.logo_label.setObjectName("channel_logo")
        self.logo_label.setFixedSize(42, 42)
        self.logo_label.setScaledContents(True)
        layout.addWidget(self.logo_label, alignment=Qt.AlignmentFlag.AlignTop)

        copy_layout = QVBoxLayout()
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("channel_row_title")
        self.title_label.setWordWrap(True)
        title_row.addWidget(self.title_label, stretch=1)

        badge_container = QWidget()
        badge_layout = QHBoxLayout(badge_container)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_layout.setSpacing(4)
        for badge_text, tone in badges:
            badge_layout.addWidget(ChannelBadge(badge_text, tone))
        badge_layout.addStretch()
        title_row.addWidget(badge_container, alignment=Qt.AlignmentFlag.AlignRight)

        copy_layout.addLayout(title_row)

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("channel_row_subtitle")
        self.subtitle_label.setWordWrap(True)
        copy_layout.addWidget(self.subtitle_label)

        self.meta_label = QLabel(meta)
        self.meta_label.setObjectName("channel_row_meta")
        self.meta_label.setWordWrap(True)
        self.meta_label.setVisible(bool(meta))
        copy_layout.addWidget(self.meta_label)

        layout.addLayout(copy_layout, stretch=1)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def _apply_logo(self, pixmap: QPixmap) -> None:
        self.logo_label.setPixmap(pixmap)

    def _on_logo_loaded(self, source: str, pixmap: object) -> None:
        if source != self._logo_source or not isinstance(pixmap, QPixmap):
            return
        self._apply_logo(pixmap)


class CollectionStateWidget(QFrame):
    def __init__(self, title: str, detail: str):
        super().__init__()
        self.setObjectName("collection_state")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 24, 22, 24)
        layout.setSpacing(8)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("state_title")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.detail_label = QLabel(detail)
        self.detail_label.setObjectName("state_detail")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)
        layout.addStretch()

    def set_content(self, title: str, detail: str) -> None:
        self.title_label.setText(title)
        self.detail_label.setText(detail)


class LeftPanel(QFrame):
    """A panel containing channel categories, lists, and EPG information."""

    def __init__(self):
        super().__init__()
        self.setObjectName("library_panel")
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setMinimumWidth(340)
        self._logo_provider = ChannelLogoProvider(self)
        self._collection_views: dict[QListWidget, tuple[QStackedWidget, CollectionStateWidget]] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QLabel("Library")
        title.setObjectName("section_title")
        layout.addWidget(title)

        self.filter_card = QFrame()
        self.filter_card.setObjectName("filter_card")
        filter_layout = QVBoxLayout(self.filter_card)
        filter_layout.setContentsMargins(16, 16, 16, 16)
        filter_layout.setSpacing(12)

        self.search_bar = SearchBar()
        filter_layout.addWidget(self.search_bar)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(10)

        self.category_combo = QComboBox()
        self.category_combo.setPlaceholderText("Category")
        controls.addWidget(self.category_combo, stretch=2)

        self.sort_combo = QComboBox()
        for label, value in SORT_OPTIONS:
            self.sort_combo.addItem(label, value)
        controls.addWidget(self.sort_combo, stretch=1)

        filter_layout.addLayout(controls)

        self.search_current_group_checkbox = QCheckBox("Filter search to current category")
        self.search_current_group_checkbox.setChecked(True)
        filter_layout.addWidget(self.search_current_group_checkbox)

        layout.addWidget(self.filter_card)

        self.tabs = QTabWidget()
        self.channel_list = self._create_list_widget("channel_list")
        self.favorites_list = self._create_list_widget("favorites_list")
        self.recent_list = self._create_list_widget("recent_list")

        self.tabs.addTab(
            self._wrap_collection(self.channel_list, "No playlist loaded", "Load a playlist to browse channels."),
            "Channels",
        )
        self.tabs.addTab(
            self._wrap_collection(self.favorites_list, "No favorites yet", "Saved channels will appear here."),
            "Favorites",
        )
        self.tabs.addTab(
            self._wrap_collection(self.recent_list, "No recent channels", "Your playback history will appear here."),
            "Recent",
        )
        layout.addWidget(self.tabs, stretch=1)

        self.epg_status_label = QLabel("EPG unavailable")
        self.epg_status_label.setObjectName("epg_status")
        layout.addWidget(self.epg_status_label)

        self.epg_widget = EPGWidget()
        layout.addWidget(self.epg_widget)

    def _create_list_widget(self, object_name: str) -> QListWidget:
        widget = QListWidget()
        widget.setObjectName(object_name)
        widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        widget.itemSelectionChanged.connect(lambda w=widget: self._sync_list_selection_styles(w))
        return widget

    def _wrap_collection(
        self,
        widget: QListWidget,
        title: str,
        detail: str,
    ) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        stacked = QStackedWidget()
        state = CollectionStateWidget(title, detail)
        stacked.addWidget(widget)
        stacked.addWidget(state)
        layout.addWidget(stacked)
        self._collection_views[widget] = (stacked, state)
        stacked.setCurrentWidget(state)
        return container

    def add_channels(
        self,
        channels: list[Channel],
        *,
        current_programs: dict[str, Program] | None = None,
        show_now_playing: bool = True,
        favorites: set[tuple[str, str]] | None = None,
        current_channel_key: tuple[str, str] | None = None,
    ) -> None:
        self._populate_list(
            self.channel_list,
            channels,
            current_programs=current_programs,
            show_now_playing=show_now_playing,
            favorites=favorites,
            current_channel_key=current_channel_key,
            empty_title="No channels match",
            empty_detail="Adjust the category or search filters to broaden the results.",
            list_kind="channels",
        )

    def add_favorites(
        self,
        channels: list[Channel],
        *,
        current_programs: dict[str, Program] | None = None,
        show_now_playing: bool = True,
        current_channel_key: tuple[str, str] | None = None,
    ) -> None:
        self._populate_list(
            self.favorites_list,
            channels,
            current_programs=current_programs,
            show_now_playing=show_now_playing,
            favorites={channel.identity_key() for channel in channels},
            current_channel_key=current_channel_key,
            empty_title="No favorite channels",
            empty_detail="Use the Favorite control while watching a channel to pin it here.",
            list_kind="favorites",
        )

    def add_recent_channels(
        self,
        channels: list[Channel],
        *,
        current_programs: dict[str, Program] | None = None,
        show_now_playing: bool = True,
        favorites: set[tuple[str, str]] | None = None,
        current_channel_key: tuple[str, str] | None = None,
    ) -> None:
        self._populate_list(
            self.recent_list,
            channels,
            current_programs=current_programs,
            show_now_playing=show_now_playing,
            favorites=favorites,
            current_channel_key=current_channel_key,
            empty_title="Nothing played recently",
            empty_detail="Recently watched channels will appear here after playback starts.",
            list_kind="recent",
        )

    def show_loading_state(self, target: str, title: str, detail: str) -> None:
        widget = self._widget_for_target(target)
        self._set_collection_state(widget, title, detail)

    def set_epg_status(self, message: str) -> None:
        self.epg_status_label.setText(message)

    def set_sort_mode(self, mode: str) -> None:
        index = self.sort_combo.findData(mode)
        if index >= 0:
            self.sort_combo.setCurrentIndex(index)

    def highlight_channel(self, channel: Channel) -> None:
        for widget in (self.channel_list, self.favorites_list, self.recent_list):
            self._select_channel(widget, channel.identity_key())

    def _populate_list(
        self,
        widget: QListWidget,
        channels: list[Channel],
        *,
        current_programs: dict[str, Program] | None,
        show_now_playing: bool,
        favorites: set[tuple[str, str]] | None,
        current_channel_key: tuple[str, str] | None,
        empty_title: str,
        empty_detail: str,
        list_kind: str,
    ) -> None:
        widget.clear()
        favorites = favorites or set()
        current_programs = current_programs or {}
        if not channels:
            self._set_collection_state(widget, empty_title, empty_detail)
            return

        self._show_collection(widget)
        for channel in channels:
            program = current_programs.get(channel.epg_id)
            is_favorite = channel.identity_key() in favorites
            is_current = channel.identity_key() == current_channel_key
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, channel)
            item.setSizeHint(QSize(100, 88))
            widget.addItem(item)
            row = self._channel_item_widget(
                channel,
                program=program,
                show_now_playing=show_now_playing,
                is_favorite=is_favorite,
                is_current=is_current,
                list_kind=list_kind,
            )
            widget.setItemWidget(item, row)

        if current_channel_key:
            self._select_channel(widget, current_channel_key)
        self._sync_list_selection_styles(widget)

    def _channel_item_widget(
        self,
        channel: Channel,
        *,
        program: Program | None,
        show_now_playing: bool,
        is_favorite: bool,
        is_current: bool,
        list_kind: str,
    ) -> ChannelListItemWidget:
        badges: list[tuple[str, str]] = []
        if is_current:
            badges.append(("LIVE", "accent"))
        if is_favorite:
            badges.append(("FAV", "warning"))

        group_name = channel.group or "Uncategorized"
        subtitle = group_name
        meta_parts: list[str] = []

        if show_now_playing and program:
            subtitle = program.title
            meta_parts.append(
                f"{self._format_display_time(program.start_time)} - "
                f"{self._format_display_time(program.end_time)}"
            )
            meta_parts.append(group_name)

        if list_kind == "recent" and channel.last_played_at:
            played_at = datetime.fromtimestamp(channel.last_played_at).strftime("%Y-%m-%d %H:%M")
            meta_parts.append(f"Last played {played_at}")
        elif list_kind == "favorites":
            meta_parts.append(f"Source {Path(channel.playlist_path or 'active').name}")

        return ChannelListItemWidget(
            channel,
            logo_provider=self._logo_provider,
            title=channel.name,
            subtitle=subtitle,
            meta="  |  ".join(part for part in meta_parts if part),
            badges=badges,
        )

    def _widget_for_target(self, target: str) -> QListWidget:
        mapping = {
            "channels": self.channel_list,
            "favorites": self.favorites_list,
            "recent": self.recent_list,
        }
        return mapping[target]

    def _set_collection_state(self, widget: QListWidget, title: str, detail: str) -> None:
        stacked, state = self._collection_views[widget]
        state.set_content(title, detail)
        stacked.setCurrentWidget(state)

    def _show_collection(self, widget: QListWidget) -> None:
        stacked, _ = self._collection_views[widget]
        stacked.setCurrentWidget(widget)

    @staticmethod
    def _format_display_time(value: datetime) -> str:
        if value.tzinfo is None:
            return value.strftime("%H:%M")
        return value.astimezone().strftime("%H:%M")

    @staticmethod
    def _select_channel(widget: QListWidget, channel_key: tuple[str, str] | None) -> None:
        if not channel_key:
            widget.clearSelection()
            return
        for index in range(widget.count()):
            item = widget.item(index)
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, Channel) and data.identity_key() == channel_key:
                widget.setCurrentRow(index)
                return

    @staticmethod
    def _sync_list_selection_styles(widget: QListWidget) -> None:
        current_item = widget.currentItem()
        for index in range(widget.count()):
            item = widget.item(index)
            child = widget.itemWidget(item)
            if isinstance(child, ChannelListItemWidget):
                child.set_selected(item is current_item)
