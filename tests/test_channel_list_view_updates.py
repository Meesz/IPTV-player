"""Data-only model updates must not relayout the channel list or move its scroll position."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QAbstractItemView, QListView

from core.models import Channel, Program
from ui.widgets.channel_list_view import ChannelListModel, ChannelListView, ChannelRowDelegate

ROW_COUNT = 2000
VISIBLE_ROW = 1100
OFFSCREEN_ROW = 1900


class _StubLogoProvider(QObject):
    logo_loaded = pyqtSignal(str, object)

    def request_logo(self, _source: str, _name: str) -> QPixmap | None:
        return None


class _RecordingDelegate(ChannelRowDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.painted_rows: list[int] = []

    def paint(self, painter, option, index):
        self.painted_rows.append(index.row())
        super().paint(painter, option, index)


@pytest.fixture
def scrolled_view(qapp):
    view = ChannelListView(_StubLogoProvider())
    delegate = _RecordingDelegate(view)
    view.setItemDelegate(delegate)
    view.set_channels(
        [
            Channel(
                name=f"Channel {i}",
                url=f"https://example.com/{i}",
                group="News",
                logo=f"https://logos.example.com/{i}.png",
                epg_id=f"epg-{i}",
            )
            for i in range(ROW_COUNT)
        ]
    )
    view.resize(360, 400)
    view.show()
    bar = view.verticalScrollBar()
    # Batched layout finishes over several event-loop turns; wait for the full scroll range.
    full_range = ROW_COUNT * ChannelRowDelegate.ROW_HEIGHT - view.viewport().height()
    for _ in range(200):
        qapp.processEvents()
        if bar.maximum() >= full_range:
            break
    assert bar.maximum() >= full_range
    bar.setValue(VISIBLE_ROW * ChannelRowDelegate.ROW_HEIGHT - 100)
    _settle(qapp)
    yield view, delegate
    view.close()


def _scroll_state(view: ChannelListView) -> tuple[int, int]:
    bar = view.verticalScrollBar()
    return bar.value(), bar.maximum()


def _program(title: str = "Evening News") -> Program:
    start = datetime(2026, 1, 1, 20, 0)
    return Program(title=title, start_time=start, end_time=start + timedelta(hours=1))


def _settle(qapp) -> None:
    for _ in range(5):
        qapp.processEvents()


def _trigger(view: ChannelListView, kind: str, row: int) -> None:
    if kind == "logo":
        view.channel_model.notify_logo_changed(f"https://logos.example.com/{row}.png")
    else:
        view.update_current_programs({f"epg-{row}": _program()})


@pytest.mark.parametrize("kind", ["logo", "program"])
@pytest.mark.parametrize("row", [VISIBLE_ROW, OFFSCREEN_ROW])
def test_data_only_update_keeps_scroll_position_and_range(qapp, scrolled_view, kind, row):
    view, _delegate = scrolled_view
    before = _scroll_state(view)
    assert before[0] > 50_000  # genuinely scrolled far down, past the 256-row batch

    _trigger(view, kind, row)
    _settle(qapp)

    assert _scroll_state(view) == before


@pytest.mark.parametrize("kind", ["logo", "program"])
def test_data_only_update_repaints_visible_row(qapp, scrolled_view, kind):
    view, delegate = scrolled_view
    assert view.indexAt(view.viewport().rect().center()).row() in range(VISIBLE_ROW - 3, VISIBLE_ROW + 4)
    delegate.painted_rows.clear()

    _trigger(view, kind, VISIBLE_ROW)
    _settle(qapp)

    assert VISIBLE_ROW in delegate.painted_rows


def test_data_only_update_does_not_repaint_offscreen_row(qapp, scrolled_view):
    view, delegate = scrolled_view
    delegate.painted_rows.clear()

    _trigger(view, "logo", OFFSCREEN_ROW)
    _settle(qapp)

    assert OFFSCREEN_ROW not in delegate.painted_rows


def test_only_data_roles_skip_the_list_view_relayout(qapp, scrolled_view, monkeypatch):
    view, _delegate = scrolled_view
    calls: list[str] = []
    monkeypatch.setattr(QListView, "dataChanged", lambda *_args: calls.append("list"))
    monkeypatch.setattr(QAbstractItemView, "dataChanged", lambda *_args: calls.append("item"))
    emit = view.channel_model.dataChanged.emit
    index = view.channel_model.index(VISIBLE_ROW)

    emit(index, index, [])
    emit(index, index, [Qt.ItemDataRole.DisplayRole])
    emit(index, index, [ChannelListModel.LogoPixmapRole, Qt.ItemDataRole.FontRole])
    assert calls == ["list", "list", "list"]

    calls.clear()
    emit(index, index, [ChannelListModel.LogoPixmapRole])
    emit(index, index, [ChannelListModel.SubtitleRole, ChannelListModel.MetaRole])
    assert calls == ["item", "item"]


def test_model_still_emits_role_specific_data_changed(qapp):
    model = ChannelListModel(_StubLogoProvider())
    model.set_channels([Channel(name="A", url="u", logo="l", epg_id="e")])
    seen: list[list[int]] = []
    model.dataChanged.connect(lambda _a, _b, roles: seen.append(list(roles)))

    model.notify_logo_changed("l")
    model.update_current_programs({"e": _program()})

    assert seen == [[ChannelListModel.LogoPixmapRole], [ChannelListModel.SubtitleRole, ChannelListModel.MetaRole]]
