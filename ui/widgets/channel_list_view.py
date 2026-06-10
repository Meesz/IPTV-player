from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QAbstractListModel, QEvent, QModelIndex, QPoint, QRect, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QListView, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QWidget

from core.models import Channel, Program
from ui.styles.themes import Themes


class ChannelListModel(QAbstractListModel):
    ChannelRole = Qt.ItemDataRole.UserRole + 1
    TitleRole = Qt.ItemDataRole.UserRole + 2
    SubtitleRole = Qt.ItemDataRole.UserRole + 3
    MetaRole = Qt.ItemDataRole.UserRole + 4
    BadgesRole = Qt.ItemDataRole.UserRole + 5
    LogoPixmapRole = Qt.ItemDataRole.UserRole + 6
    LogoSourceRole = Qt.ItemDataRole.UserRole + 7

    def __init__(
        self,
        logo_provider,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._logo_provider = logo_provider
        self._channels: list[Channel] = []
        self._favorite_keys: set[tuple[str, str]] = set()
        self._current_channel_key: tuple[str, str] | None = None
        self._show_now_playing = True
        self._programs_by_epg_id: dict[str, Program] = {}
        self._rows_by_logo_source: dict[str, list[int]] = {}
        self._rows_by_epg_id: dict[str, list[int]] = {}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._channels)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._channels):
            return None

        channel = self._channels[index.row()]
        program = self._programs_by_epg_id.get(channel.epg_id)

        if role == Qt.ItemDataRole.DisplayRole or role == self.TitleRole:
            return channel.name
        if role == self.ChannelRole:
            return channel
        if role == self.SubtitleRole:
            if self._show_now_playing and program:
                return program.title
            return channel.group or "Uncategorized"
        if role == self.MetaRole:
            if not (self._show_now_playing and program):
                return ""
            return (
                f"{self._format_display_time(program.start_time)} - "
                f"{self._format_display_time(program.end_time)}  |  "
                f"{channel.group or 'Uncategorized'}"
            )
        if role == self.BadgesRole:
            badges: list[tuple[str, str]] = []
            if channel.identity_key() == self._current_channel_key:
                badges.append(("LIVE", "accent"))
            if channel.identity_key() in self._favorite_keys:
                badges.append(("FAV", "warning"))
            return badges
        if role == self.LogoSourceRole:
            return channel.logo
        if role == self.LogoPixmapRole:
            return self._logo_provider.request_logo(channel.logo, channel.name)
        if role == Qt.ItemDataRole.SizeHintRole:
            return QSize(100, 88)
        return None

    def set_channels(
        self,
        channels: list[Channel],
        *,
        favorite_keys: set[tuple[str, str]] | None = None,
        current_channel_key: tuple[str, str] | None = None,
        show_now_playing: bool = True,
    ) -> None:
        self.beginResetModel()
        self._channels = list(channels)
        self._favorite_keys = set(favorite_keys or set())
        self._current_channel_key = current_channel_key
        self._show_now_playing = show_now_playing
        self._programs_by_epg_id = {}
        self._rows_by_logo_source = {}
        self._rows_by_epg_id = {}
        for row, channel in enumerate(self._channels):
            if channel.logo:
                self._rows_by_logo_source.setdefault(channel.logo, []).append(row)
            if channel.epg_id:
                self._rows_by_epg_id.setdefault(channel.epg_id, []).append(row)
        self.endResetModel()

    def clear(self) -> None:
        self.set_channels([])

    def channel_at(self, row: int) -> Channel | None:
        if 0 <= row < len(self._channels):
            return self._channels[row]
        return None

    def row_for_channel_key(self, channel_key: tuple[str, str] | None) -> int:
        if channel_key is None:
            return -1
        for row, channel in enumerate(self._channels):
            if channel.identity_key() == channel_key:
                return row
        return -1

    def update_current_programs(self, programs: dict[str, Program]) -> None:
        if not programs:
            return
        changed_rows: set[int] = set()
        for epg_id, program in programs.items():
            self._programs_by_epg_id[epg_id] = program
            changed_rows.update(self._rows_by_epg_id.get(epg_id, []))
        for row in sorted(changed_rows):
            index = self.index(row)
            self.dataChanged.emit(
                index,
                index,
                [self.SubtitleRole, self.MetaRole],
            )

    def notify_logo_changed(self, source: str) -> None:
        for row in self._rows_by_logo_source.get(source, []):
            index = self.index(row)
            self.dataChanged.emit(index, index, [self.LogoPixmapRole])

    @staticmethod
    def _format_display_time(value: datetime) -> str:
        if value.tzinfo is None:
            return value.strftime("%H:%M")
        return value.astimezone().strftime("%H:%M")


class ChannelRowDelegate(QStyledItemDelegate):
    ROW_HEIGHT = 88
    LOGO_SIZE = 42

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._tokens = Themes._DARK

    def set_theme_mode(self, mode: str) -> None:
        self._tokens = Themes._LIGHT if mode == "light" else Themes._DARK

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            rect = option.rect.adjusted(0, 4, 0, -4)
            selected = bool(option.state & QStyle.StateFlag.State_Selected)
            hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

            background = QColor(self._tokens["surface_hover"] if hovered else self._tokens["surface"])
            border = QColor(self._tokens["border_soft"])
            if selected:
                background = QColor(self._tokens["selection"])
                border = QColor(self._tokens["accent"])

            path = QPainterPath()
            path.addRoundedRect(QRectF(rect), 14, 14)
            painter.fillPath(path, background)
            painter.setPen(QPen(border, 1))
            painter.drawPath(path)

            content_rect = rect.adjusted(14, 12, -14, -12)
            logo_rect = QRect(
                content_rect.left(),
                content_rect.top(),
                self.LOGO_SIZE,
                self.LOGO_SIZE,
            )
            logo_bg = QPainterPath()
            logo_bg.addRoundedRect(QRectF(logo_rect), 12, 12)
            painter.fillPath(logo_bg, QColor(self._tokens["panel_alt"]))
            painter.setPen(QPen(QColor(self._tokens["border_soft"]), 1))
            painter.drawPath(logo_bg)

            pixmap = index.data(ChannelListModel.LogoPixmapRole)
            if pixmap is not None:
                painter.setClipPath(logo_bg)
                painter.drawPixmap(logo_rect, pixmap)
                painter.setClipping(False)

            text_left = logo_rect.right() + 12
            text_width = max(0, content_rect.right() - text_left)
            text_rect = QRect(text_left, content_rect.top(), text_width, content_rect.height())

            title = str(index.data(ChannelListModel.TitleRole) or "")
            subtitle = str(index.data(ChannelListModel.SubtitleRole) or "")
            meta = str(index.data(ChannelListModel.MetaRole) or "")
            badges = list(index.data(ChannelListModel.BadgesRole) or [])

            badges_width = self._paint_badges(painter, text_rect, badges)
            title_rect = QRect(
                text_rect.left(),
                text_rect.top(),
                max(0, text_rect.width() - badges_width - 8),
                22,
            )
            subtitle_rect = QRect(text_rect.left(), text_rect.top() + 26, text_rect.width(), 18)
            meta_rect = QRect(text_rect.left(), text_rect.top() + 48, text_rect.width(), 18)

            title_font = QFont(option.font)
            title_font.setBold(True)
            painter.setFont(title_font)
            painter.setPen(QColor(self._tokens["text"]))
            title_metrics = painter.fontMetrics()
            painter.drawText(
                title_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                title_metrics.elidedText(title, Qt.TextElideMode.ElideRight, title_rect.width()),
            )

            subtitle_font = QFont(option.font)
            subtitle_font.setBold(False)
            painter.setFont(subtitle_font)
            painter.setPen(QColor(self._tokens["muted"]))
            subtitle_metrics = painter.fontMetrics()
            painter.drawText(
                subtitle_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                subtitle_metrics.elidedText(
                    subtitle,
                    Qt.TextElideMode.ElideRight,
                    subtitle_rect.width(),
                ),
            )

            if meta:
                painter.drawText(
                    meta_rect,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    subtitle_metrics.elidedText(meta, Qt.TextElideMode.ElideRight, meta_rect.width()),
                )
        finally:
            painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return QSize(option.rect.width(), self.ROW_HEIGHT)

    def _paint_badges(
        self,
        painter: QPainter,
        text_rect: QRect,
        badges: list[tuple[str, str]],
    ) -> int:
        if not badges:
            return 0

        badge_font = QFont(painter.font())
        badge_font.setBold(True)
        badge_font.setPointSize(max(10, badge_font.pointSize() - 1))
        painter.setFont(badge_font)
        metrics = painter.fontMetrics()
        x = text_rect.right()
        total_width = 0

        for badge_text, tone in reversed(badges):
            badge_width = metrics.horizontalAdvance(badge_text) + 16
            badge_rect = QRect(x - badge_width, text_rect.top() + 1, badge_width, 20)
            badge_bg = QColor(self._tokens["accent_soft"])
            badge_fg = QColor(self._tokens["warning"] if tone == "warning" else self._tokens["accent"])

            path = QPainterPath()
            path.addRoundedRect(QRectF(badge_rect), 10, 10)
            painter.fillPath(path, badge_bg)
            painter.setPen(badge_fg)
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

            x -= badge_width + 6
            total_width += badge_width + 6

        return total_width


class ChannelListView(QListView):
    channel_clicked = pyqtSignal(object)
    channel_activated = pyqtSignal(object)
    visible_channels_changed = pyqtSignal()

    def __init__(
        self,
        logo_provider,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("channel_list")
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.setUniformItemSizes(True)
        self.setMouseTracking(True)
        self.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        self.setLayoutMode(QListView.LayoutMode.Batched)
        self.setBatchSize(256)

        self._model = ChannelListModel(logo_provider, self)
        self._delegate = ChannelRowDelegate(self)
        self.setModel(self._model)
        self.setItemDelegate(self._delegate)

        self._visible_channels_timer = QTimer(self)
        self._visible_channels_timer.setSingleShot(True)
        self._visible_channels_timer.timeout.connect(self.visible_channels_changed.emit)

        logo_provider.logo_loaded.connect(self._on_logo_loaded)
        self.clicked.connect(self._emit_channel_clicked)
        self.doubleClicked.connect(self._emit_channel_activated)
        self.verticalScrollBar().valueChanged.connect(self._schedule_visible_channels_changed)
        self.installEventFilter(self)

    @property
    def channel_model(self) -> ChannelListModel:
        return self._model

    def set_theme_mode(self, mode: str) -> None:
        self._delegate.set_theme_mode(mode)
        self.viewport().update()

    def set_channels(
        self,
        channels: list[Channel],
        *,
        favorite_keys: set[tuple[str, str]] | None = None,
        current_channel_key: tuple[str, str] | None = None,
        show_now_playing: bool = True,
    ) -> None:
        self._model.set_channels(
            channels,
            favorite_keys=favorite_keys,
            current_channel_key=current_channel_key,
            show_now_playing=show_now_playing,
        )
        self.clearSelection()
        self._schedule_visible_channels_changed()

    def clear_channels(self) -> None:
        self._model.clear()
        self.clearSelection()

    def update_current_programs(self, programs: dict[str, Program]) -> None:
        self._model.update_current_programs(programs)

    def select_channel_key(self, channel_key: tuple[str, str] | None) -> None:
        row = self._model.row_for_channel_key(channel_key)
        if row < 0:
            self.clearSelection()
            return
        index = self._model.index(row)
        self.setCurrentIndex(index)
        self.scrollTo(index, QListView.ScrollHint.PositionAtCenter)

    def visible_channels(self) -> list[Channel]:
        row_count = self._model.rowCount()
        if row_count == 0:
            return []

        top_index = self.indexAt(QPoint(8, 8))
        bottom_index = self.indexAt(QPoint(8, max(8, self.viewport().height() - 8)))

        start_row = top_index.row() if top_index.isValid() else 0
        if bottom_index.isValid():
            end_row = bottom_index.row()
        else:
            estimated = max(1, self.viewport().height() // ChannelRowDelegate.ROW_HEIGHT + 1)
            end_row = min(row_count - 1, start_row + estimated)

        return [
            channel
            for row in range(start_row, min(end_row + 1, row_count))
            if (channel := self._model.channel_at(row)) is not None
        ]

    def cancel_pending_updates(self) -> None:
        self._visible_channels_timer.stop()

    def eventFilter(self, watched: object, event: QEvent) -> bool:
        if watched is self and event.type() in {
            QEvent.Type.Show,
            QEvent.Type.Resize,
        }:
            self._schedule_visible_channels_changed()
        return super().eventFilter(watched, event)

    def _emit_channel_clicked(self, index: QModelIndex) -> None:
        channel = index.data(ChannelListModel.ChannelRole)
        if isinstance(channel, Channel):
            self.channel_clicked.emit(channel)

    def _emit_channel_activated(self, index: QModelIndex) -> None:
        channel = index.data(ChannelListModel.ChannelRole)
        if isinstance(channel, Channel):
            self.channel_activated.emit(channel)

    def _on_logo_loaded(self, source: str, _pixmap: object) -> None:
        self._model.notify_logo_changed(source)

    def _schedule_visible_channels_changed(self) -> None:
        self._visible_channels_timer.start(50)
