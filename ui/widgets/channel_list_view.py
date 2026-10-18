from __future__ import annotations

from PyQt6.QtCore import QAbstractListModel, QEvent, QModelIndex, QPoint, QRect, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QListView, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QWidget

from core.models import Channel, Program
from ui.styles.themes import Themes
from ui.utils.time_format import format_display_time


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
        self._meta_suffixes: dict[int, str] = {}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008  (QModelIndex() is the standard Qt override default)
        if parent.isValid():
            return 0
        return len(self._channels)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: PLR0911  (role dispatch)
        if not index.isValid() or not 0 <= index.row() < len(self._channels):
            return None

        channel = self._channels[index.row()]
        program = self._programs_by_epg_id.get(channel.epg_id)

        if role in (Qt.ItemDataRole.DisplayRole, self.TitleRole):
            return channel.name
        if role == self.ChannelRole:
            return channel
        if role == self.SubtitleRole:
            if self._show_now_playing and program:
                return program.title
            return channel.group or "Uncategorized"
        if role == self.MetaRole:
            suffix = self._meta_suffixes.get(index.row(), "")
            if not (self._show_now_playing and program):
                return suffix
            epg_meta = (
                f"{format_display_time(program.start_time)} - "
                f"{format_display_time(program.end_time)}  |  "
                f"{channel.group or 'Uncategorized'}"
            )
            return f"{epg_meta}  |  {suffix}" if suffix else epg_meta
        if role == self.BadgesRole:
            badges: list[tuple[str, str]] = []
            if channel.identity_key() == self._current_channel_key:
                badges.append(("PLAYING", "live"))
            if channel.identity_key() in self._favorite_keys:
                badges.append(("FAV", "warning"))
            return badges
        if role == self.LogoSourceRole:
            return channel.logo
        if role == self.LogoPixmapRole:
            return self._logo_provider.request_logo(channel.logo, channel.name)
        return None

    def set_channels(
        self,
        channels: list[Channel],
        *,
        favorite_keys: set[tuple[str, str]] | None = None,
        current_channel_key: tuple[str, str] | None = None,
        show_now_playing: bool = True,
        meta_suffixes: dict[int, str] | None = None,
    ) -> None:
        self.beginResetModel()
        self._channels = list(channels)
        self._favorite_keys = set(favorite_keys or set())
        self._current_channel_key = current_channel_key
        self._show_now_playing = show_now_playing
        self._meta_suffixes = meta_suffixes or {}
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


class ChannelRowDelegate(QStyledItemDelegate):
    """Flat, hairline-separated channel rows painted with painter-safe theme colors."""

    LOGO_SIZE = 36
    ROW_HEIGHT = 70
    _PAD_X = 12
    _PAD_Y = 8
    _BAR_WIDTH = 3

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._mode = "dark"

    def set_theme_mode(self, mode: str) -> None:
        self._mode = mode

    def _color(self, key: str) -> QColor:
        return Themes.color(self._mode, key)

    @staticmethod
    def _font(base: QFont, pixel_size: int, *, semibold: bool) -> QFont:
        font = QFont(base)
        font.setPixelSize(pixel_size)
        font.setWeight(QFont.Weight.DemiBold if semibold else QFont.Weight.Normal)
        return font

    @staticmethod
    def _secondary_lines(subtitle: str, meta: str) -> list[str]:
        """Secondary text lines, without repeating the subtitle that meta already contains."""
        if subtitle and meta and subtitle in (part.strip() for part in meta.split("|")):
            return [meta]
        return [line for line in (subtitle, meta) if line]

    def paint(  # noqa: PLR0915  (custom delegate painting)
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

            rect = option.rect
            selected = bool(option.state & QStyle.StateFlag.State_Selected)
            hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

            fill: QColor | None = None
            if selected:
                fill = self._color("accent_soft")
            elif hovered:
                fill = self._color("row_hover")
            if fill is not None:
                path = QPainterPath()
                path.addRoundedRect(QRectF(rect.adjusted(4, 2, -4, -2)), 8, 8)
                painter.fillPath(path, fill)

            # Hairline separator between rows.
            painter.setPen(QPen(self._color("hairline"), 1))
            painter.drawLine(rect.left() + self._PAD_X, rect.bottom(), rect.right() - self._PAD_X, rect.bottom())

            title = str(index.data(ChannelListModel.TitleRole) or "")
            subtitle = str(index.data(ChannelListModel.SubtitleRole) or "")
            meta = str(index.data(ChannelListModel.MetaRole) or "")
            badges = list(index.data(ChannelListModel.BadgesRole) or [])
            playing = any(text == "PLAYING" for text, _tone in badges)

            if playing:
                bar = QPainterPath()
                bar.addRoundedRect(
                    QRectF(rect.left() + 1, rect.top() + 10, self._BAR_WIDTH, rect.height() - 20),
                    1.5,
                    1.5,
                )
                painter.fillPath(bar, self._color("live"))

            content = rect.adjusted(self._PAD_X + 2, self._PAD_Y, -self._PAD_X, -self._PAD_Y)
            logo_rect = QRect(
                content.left(),
                rect.top() + (rect.height() - self.LOGO_SIZE) // 2,
                self.LOGO_SIZE,
                self.LOGO_SIZE,
            )
            self._paint_logo(painter, logo_rect, index.data(ChannelListModel.LogoPixmapRole))

            text_left = logo_rect.right() + 1 + 12
            text_rect = QRect(text_left, content.top(), max(0, content.right() + 1 - text_left), content.height())

            title_font = self._font(option.font, 13, semibold=True)
            # Subtitle (12px, muted) then meta (11px, faint); both must fit under the title.
            line_fonts = (
                self._font(option.font, 12, semibold=False),
                self._font(option.font, 11, semibold=False),
            )
            painter.setFont(title_font)
            title_h = painter.fontMetrics().height()

            badges_width = self._paint_badges(
                painter, QRect(text_rect.left(), text_rect.top(), text_rect.width(), title_h), badges
            )
            title_rect = QRect(
                text_rect.left(),
                text_rect.top(),
                max(0, text_rect.width() - (badges_width + 8 if badges_width else 0)),
                title_h,
            )
            painter.setFont(title_font)
            painter.setPen(self._color("text"))
            painter.drawText(
                title_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                painter.fontMetrics().elidedText(title, Qt.TextElideMode.ElideRight, title_rect.width()),
            )

            y = text_rect.top() + title_h + 2
            for position, line in enumerate(self._secondary_lines(subtitle, meta)):
                painter.setFont(line_fonts[min(position, 1)])
                metrics = painter.fontMetrics()
                line_h = metrics.height()
                if y + line_h > rect.bottom() - 1:
                    break
                painter.setPen(self._color("muted" if position == 0 else "faint"))
                line_rect = QRect(text_rect.left(), y, text_rect.width(), line_h)
                painter.drawText(
                    line_rect,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    metrics.elidedText(line, Qt.TextElideMode.ElideRight, line_rect.width()),
                )
                y += line_h
        finally:
            painter.restore()

    def _paint_logo(self, painter: QPainter, logo_rect: QRect, pixmap: object) -> None:
        logo_bg = QPainterPath()
        logo_bg.addRoundedRect(QRectF(logo_rect), 8, 8)
        painter.fillPath(logo_bg, self._color("raised"))
        if pixmap is None or pixmap.isNull():
            return
        side = min(pixmap.width(), pixmap.height())
        source = QRect((pixmap.width() - side) // 2, (pixmap.height() - side) // 2, side, side)
        painter.save()
        painter.setClipPath(logo_bg)
        painter.drawPixmap(logo_rect, pixmap, source)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        # Width is intentionally small and independent of option.rect: the view stretches rows
        # to the viewport, and a stale rect width would create a horizontal scroll range.
        return QSize(1, self.ROW_HEIGHT)

    def _paint_badges(
        self,
        painter: QPainter,
        title_line: QRect,
        badges: list[tuple[str, str]],
    ) -> int:
        """Paint right-aligned status markers on the title line and return the width used."""
        if not badges:
            return 0

        marker_font = self._font(painter.font(), 11, semibold=True)
        painter.setFont(marker_font)
        metrics = painter.fontMetrics()
        x = title_line.right() + 1
        total_width = 0

        for badge_text, tone in reversed(badges):
            glyph = "★" if badge_text == "FAV" else badge_text
            width = metrics.horizontalAdvance(glyph)
            badge_rect = QRect(x - width, title_line.top(), width, title_line.height())
            painter.setPen(self._color("warning" if tone == "warning" else "live"))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, glyph)
            x -= width + 8
            total_width += width + 8

        return max(0, total_width - 8)


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
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
        meta_suffixes: dict[int, str] | None = None,
    ) -> None:
        self._model.set_channels(
            channels,
            favorite_keys=favorite_keys,
            current_channel_key=current_channel_key,
            show_now_playing=show_now_playing,
            meta_suffixes=meta_suffixes,
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
