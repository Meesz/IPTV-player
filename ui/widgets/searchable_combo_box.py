"""QComboBox whose popup has a search field above a filtered item list."""

from __future__ import annotations

from collections.abc import Iterable

from PyQt6.QtCore import QEvent, QModelIndex, QObject, QPoint, QRect, QSortFilterProxyModel, Qt
from PyQt6.QtGui import QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QLabel,
    QLineEdit,
    QListView,
    QVBoxLayout,
    QWidget,
)

_POPUP_MAX_LIST_HEIGHT = 300
_POPUP_MIN_WIDTH = 260


class _PinnedFilterProxy(QSortFilterProxyModel):
    """Case-insensitive substring filter that always keeps pinned items visible."""

    def __init__(self, pinned_texts: Iterable[str], parent: QObject | None = None):
        super().__init__(parent)
        self._pinned = frozenset(pinned_texts)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def is_pinned(self, source_row: int) -> bool:
        source = self.sourceModel()
        if source is None:
            return False
        return source.index(source_row, 0).data() in self._pinned

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if self.is_pinned(source_row):
            return True
        return super().filterAcceptsRow(source_row, source_parent)


class _SearchPopup(QFrame):
    def __init__(self, combo: SearchableComboBox, empty_text: str):
        super().__init__(combo, Qt.WindowType.Popup)
        self.setObjectName("searchable_combo_popup")
        self._combo = combo

        self.search_field = QLineEdit(self)
        self.search_field.setClearButtonEnabled(True)
        self.search_field.installEventFilter(self)

        self.list_view = QListView(self)
        self.list_view.setUniformItemSizes(True)
        self.list_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.list_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_view.setTextElideMode(Qt.TextElideMode.ElideRight)

        self.empty_label = QLabel(empty_text, self)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        layout.addWidget(self.search_field)
        layout.addWidget(self.list_view, stretch=1)
        layout.addWidget(self.empty_label)

    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:
        if watched is self.search_field and event is not None and event.type() == QEvent.Type.KeyPress:
            assert isinstance(event, QKeyEvent)
            key = event.key()
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_PageDown, Qt.Key.Key_PageUp):
                self._combo._move_popup_selection(key)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._combo._choose_popup_index(self.list_view.currentIndex())
                return True
            if key == Qt.Key.Key_Escape:
                self._combo.hidePopup()
                return True
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        # A press outside closes the popup and is replayed to the widget underneath; on the
        # combo itself that would reopen the popup straight away.
        if event is not None:
            combo_rect = QRect(self._combo.mapToGlobal(QPoint(0, 0)), self._combo.size())
            on_combo = combo_rect.contains(event.globalPosition().toPoint())
            self.setAttribute(Qt.WidgetAttribute.WA_NoMouseReplay, on_combo)
        super().mousePressEvent(event)


class SearchableComboBox(QComboBox):
    """Combo box with the standard closed look whose popup can be filtered by typing.

    Items whose text is in ``pinned_texts`` stay visible whatever the filter. The public
    QComboBox API (items, current index/text, signals) is unchanged.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        search_placeholder: str = "Search",
        empty_text: str = "No matches",
        pinned_texts: Iterable[str] = (),
    ):
        super().__init__(parent)
        self._proxy = _PinnedFilterProxy(pinned_texts, self)
        self._proxy.setSourceModel(self.model())
        self._popup = _SearchPopup(self, empty_text)
        self._popup.search_field.setPlaceholderText(search_placeholder)
        self._popup.list_view.setModel(self._proxy)
        self._popup.list_view.clicked.connect(self._choose_popup_index)
        self._popup.search_field.textChanged.connect(self._apply_filter)

    @property
    def search_field(self) -> QLineEdit:
        return self._popup.search_field

    @property
    def popup_list(self) -> QListView:
        return self._popup.list_view

    @property
    def empty_label(self) -> QLabel:
        return self._popup.empty_label

    def is_popup_visible(self) -> bool:
        return self._popup.isVisible()

    def showPopup(self) -> None:
        if self.count() == 0:
            return
        self._popup.resize(max(self.width(), _POPUP_MIN_WIDTH), self._popup.height())
        self._popup.search_field.clear()
        self._apply_filter("")
        self._popup.move(self._popup_position())
        self._popup.show()
        self._popup.search_field.setFocus(Qt.FocusReason.PopupFocusReason)
        current = self.popup_list.currentIndex()
        if current.isValid():
            self.popup_list.scrollTo(current, QAbstractItemView.ScrollHint.PositionAtCenter)

    def _popup_position(self) -> QPoint:
        below = self.mapToGlobal(QPoint(0, self.height()))
        screen = self.screen()
        if screen is None:
            return below
        available = screen.availableGeometry()
        height = self._popup.height()
        if below.y() + height > available.bottom():
            above = self.mapToGlobal(QPoint(0, -height))
            if above.y() >= available.top():
                return above
        return below

    def hidePopup(self) -> None:
        self._popup.hide()

    def _apply_filter(self, text: str) -> None:
        self._proxy.setFilterFixedString(text)
        view = self.popup_list
        source = self.model()
        if text:
            target = self._first_unpinned_proxy_index()
        elif source is not None:
            target = self._proxy.mapFromSource(source.index(self.currentIndex(), 0))
        else:
            target = QModelIndex()
        view.setCurrentIndex(target)
        self._popup.empty_label.setVisible(bool(text) and not target.isValid())
        self._fit_popup_height()

    def _fit_popup_height(self) -> None:
        view = self.popup_list
        rows = self._proxy.rowCount()
        row_height = view.sizeHintForRow(0) if rows else 0
        # Frame plus the 4px item-view padding from the theme stylesheet.
        chrome = 2 * (view.frameWidth() + 4)
        view.setFixedHeight(min(rows * row_height + chrome, _POPUP_MAX_LIST_HEIGHT))
        layout = self._popup.layout()
        if layout is not None:
            layout.activate()
        self._popup.resize(self._popup.width(), self._popup.sizeHint().height())

    def _first_unpinned_proxy_index(self) -> QModelIndex:
        for row in range(self._proxy.rowCount()):
            index = self._proxy.index(row, 0)
            if not self._proxy.is_pinned(self._proxy.mapToSource(index).row()):
                return index
        return QModelIndex()

    def _move_popup_selection(self, key: int) -> None:
        rows = self._proxy.rowCount()
        if rows == 0:
            return
        view = self.popup_list
        current = view.currentIndex().row() if view.currentIndex().isValid() else -1
        viewport = view.viewport()
        page = max(1, (viewport.height() if viewport else 0) // max(1, view.sizeHintForRow(0)))
        step = {
            Qt.Key.Key_Down: 1,
            Qt.Key.Key_Up: -1,
            Qt.Key.Key_PageDown: page,
            Qt.Key.Key_PageUp: -page,
        }[Qt.Key(key)]
        row = min(max(current + step, 0), rows - 1)
        index = self._proxy.index(row, 0)
        view.setCurrentIndex(index)
        view.scrollTo(index)

    def _choose_popup_index(self, proxy_index: QModelIndex) -> None:
        if not proxy_index.isValid():
            return
        row = self._proxy.mapToSource(proxy_index).row()
        self.setCurrentIndex(row)
        self.hidePopup()
        self.activated.emit(row)
