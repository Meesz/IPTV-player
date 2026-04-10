from datetime import datetime

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QTabWidget,
    QVBoxLayout,
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


class LeftPanel(QFrame):
    """A panel containing channel categories, lists, and EPG information."""

    def __init__(self):
        super().__init__()
        self.setObjectName("library_panel")
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setMinimumWidth(340)
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
        self.channel_list = QListWidget()
        self.channel_list.setObjectName("channel_list")
        self.favorites_list = QListWidget()
        self.favorites_list.setObjectName("favorites_list")
        self.recent_list = QListWidget()
        self.recent_list.setObjectName("recent_list")

        for widget in (self.channel_list, self.favorites_list, self.recent_list):
            widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)

        self.tabs.addTab(self.channel_list, "Channels")
        self.tabs.addTab(self.favorites_list, "Favorites")
        self.tabs.addTab(self.recent_list, "Recent")
        layout.addWidget(self.tabs, stretch=1)

        self.epg_status_label = QLabel("EPG unavailable")
        self.epg_status_label.setObjectName("epg_status")
        layout.addWidget(self.epg_status_label)

        self.epg_widget = EPGWidget()
        layout.addWidget(self.epg_widget)

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
            empty_message="Load a playlist to browse channels.",
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
            empty_message="Favorite channels appear here.",
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
            empty_message="Recently played channels appear here.",
        )

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
        empty_message: str,
    ) -> None:
        widget.clear()
        favorites = favorites or set()
        current_programs = current_programs or {}
        if not channels:
            widget.addItem(self._empty_item(empty_message))
            return

        for channel in channels:
            program = current_programs.get(channel.epg_id)
            item = self._channel_item(
                channel,
                program=program,
                show_now_playing=show_now_playing,
                is_favorite=channel.identity_key() in favorites,
                is_current=channel.identity_key() == current_channel_key,
            )
            widget.addItem(item)

        if current_channel_key:
            self._select_channel(widget, current_channel_key)

    @staticmethod
    def _channel_item(
        channel: Channel,
        *,
        program: Program | None,
        show_now_playing: bool,
        is_favorite: bool,
        is_current: bool,
    ) -> QListWidgetItem:
        title = channel.name
        if is_current:
            title = f"{title} [PLAYING]"
        elif is_favorite:
            title = f"{title} [FAV]"

        details = []
        if show_now_playing and program:
            details.append(program.title)
        elif channel.group:
            details.append(channel.group)

        if channel.last_played_at:
            played_at = datetime.fromtimestamp(channel.last_played_at).strftime("%Y-%m-%d %H:%M")
            details.append(f"Last played {played_at}")

        text = "\n".join([title, *details]) if details else title
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, channel)
        item.setToolTip(
            "\n".join(
                [
                    f"Name: {channel.name}",
                    f"Group: {channel.group or 'Uncategorized'}",
                    f"URL: {channel.url}",
                    f"Playlist: {channel.playlist_path or 'Active playlist'}",
                ]
            )
        )
        size_hint = item.sizeHint()
        item.setSizeHint(QSize(size_hint.width(), 62 if details else 52))
        return item

    @staticmethod
    def _empty_item(message: str) -> QListWidgetItem:
        item = QListWidgetItem(message)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setSizeHint(QSize(100, 52))
        return item

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
