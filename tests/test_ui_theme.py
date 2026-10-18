"""Theme token and rendered-defect regression tests for the channel list."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QStyle,
    QStyleOptionViewItem,
    QTreeView,
    QWidget,
)

from core.models import Channel
from ui.styles.themes import Themes
from ui.widgets.channel_list_view import ChannelListModel, ChannelListView, ChannelRowDelegate
from ui.widgets.left_panel import ChannelLogoProvider, LeftPanel

MODES = ("dark", "light")


@pytest.mark.parametrize("mode", MODES)
def test_every_token_is_a_valid_painter_color(mode):
    tokens = Themes.tokens(mode)
    assert tokens
    for key, value in tokens.items():
        assert QColor(value).isValid(), f"{mode}.{key}={value!r} is not a valid QColor"
        assert value.startswith("#"), f"{mode}.{key} must be a hex color, not a CSS string"


@pytest.mark.parametrize("mode", MODES)
def test_theme_color_returns_valid_qcolor(qapp, mode):
    for key in Themes.tokens(mode):
        assert Themes.color(mode, key).isValid()
    assert Themes.color("light", "panel") == QColor("#FFFFFF")
    assert Themes.color("dark", "bg") == QColor("#0E1013")
    with pytest.raises(KeyError):
        Themes.color(mode, "does_not_exist")


def test_both_themes_share_token_keys_and_build_stylesheets(qapp):
    assert set(Themes.tokens("dark")) == set(Themes.tokens("light"))
    for sheet in (Themes.get_dark_theme(), Themes.get_light_theme()):
        assert "QPushButton" in sheet
        assert "{" in sheet
        assert "qlineargradient" not in sheet


def _make_view(qapp, count: int = 20, width: int = 360, height: int = 400) -> ChannelListView:
    provider = ChannelLogoProvider()
    view = ChannelListView(provider)
    channels = [
        Channel(
            name=f"A very long channel name number {i} that should be elided instead of scrolling",
            url=f"https://example.com/{i}",
            group="Entertainment",
        )
        for i in range(count)
    ]
    view.set_channels(channels)
    view.resize(width, height)
    view.show()
    qapp.processEvents()
    return view


def test_channel_list_has_no_horizontal_scroll_range(qapp):
    view = _make_view(qapp)
    try:
        assert view.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        assert view.horizontalScrollBar().maximum() == 0
        index = view.model().index(0, 0)
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 5000, 10)
        hint = view.itemDelegate().sizeHint(option, index)
        assert hint.width() <= view.viewport().width()
        assert hint.height() <= 70
    finally:
        view.close()


def test_channel_rows_are_compact_enough_for_five_rows(qapp):
    # At the 70px row height needed for title + subtitle + meta, a 400px view shows >= 5 rows.
    view = _make_view(qapp, height=400)
    try:
        row_height = view.sizeHintForRow(0)
        assert 0 < row_height <= 70
        assert view.viewport().height() // row_height >= 5
    finally:
        view.close()


def test_tab_bar_fits_without_scroll_buttons(qapp):
    panel = LeftPanel()
    panel.resize(340, 600)
    panel.show()
    qapp.processEvents()
    try:
        tab_bar = panel.tabs.tabBar()
        assert not tab_bar.usesScrollButtons()
        assert tab_bar.sizeHint().width() <= panel.tabs.width()
    finally:
        panel.close()


def _render_row(
    mode: str,
    *,
    selected: bool,
    badges_current: bool = False,
    meta_suffix: str = "",
) -> QImage:
    provider = ChannelLogoProvider()
    view = ChannelListView(provider)
    channel = Channel(name="News Live", url="https://example.com/news", group="News")
    view.set_channels(
        [channel],
        favorite_keys={channel.identity_key()},
        current_channel_key=channel.identity_key() if badges_current else None,
        meta_suffixes={0: meta_suffix} if meta_suffix else None,
    )
    view.set_theme_mode(mode)
    delegate = view.itemDelegate()
    height = ChannelRowDelegate.ROW_HEIGHT
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 360, height)
    option.font = view.font()
    if selected:
        option.state |= QStyle.StateFlag.State_Selected
    image = QImage(360, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("#FFFFFF") if mode == "light" else QColor("#15181C"))
    painter = QPainter(image)
    try:
        delegate.paint(painter, option, view.model().index(0, 0))
    finally:
        painter.end()
    return image


def test_light_theme_unselected_row_background_is_not_black(qapp):
    image = _render_row("light", selected=False)
    # Sample plain background areas away from logo and text.
    for x, y in ((200, 4), (340, 32), (340, 50), (120, 66)):
        color = image.pixelColor(x, y)
        assert (color.red(), color.green(), color.blue()) != (0, 0, 0)
        assert color.red() > 200 and color.green() > 200 and color.blue() > 200


def test_selected_row_uses_accent_soft_in_both_themes(qapp):
    for mode in MODES:
        image = _render_row(mode, selected=True)
        expected = Themes.color(mode, "accent_soft")
        assert image.pixelColor(340, 32) == expected


def _text_pixels_in_band(image: QImage, top: int, bottom: int, background: QColor) -> int:
    return sum(
        1 for y in range(top, bottom) for x in range(60, image.width() - 20) if image.pixelColor(x, y) != background
    )


@pytest.mark.parametrize("mode", MODES)
def test_row_paints_title_subtitle_and_meta_lines(qapp, mode):
    background = QColor("#FFFFFF") if mode == "light" else QColor("#15181C")
    height = ChannelRowDelegate.ROW_HEIGHT
    # Band below the subtitle line and above the bottom hairline: only the meta line can paint here.
    top, bottom = height - 22, height - 3

    with_meta = _render_row(mode, selected=False, meta_suffix="Last played 21:04")
    without_meta = _render_row(mode, selected=False)

    assert _text_pixels_in_band(with_meta, top, bottom, background) > 20
    assert _text_pixels_in_band(without_meta, top, bottom, background) == 0


def test_playing_row_draws_live_accent_bar(qapp):
    image = _render_row("dark", selected=False, badges_current=True)
    live = Themes.color("dark", "live")
    assert image.pixelColor(2, 32) == live


def test_badge_roles_mark_playing_and_favorite(qapp):
    channel = Channel(name="X", url="https://example.com/x")
    view = ChannelListView(ChannelLogoProvider())
    view.set_channels(
        [channel],
        favorite_keys={channel.identity_key()},
        current_channel_key=channel.identity_key(),
    )
    badges = view.model().index(0, 0).data(ChannelListModel.BadgesRole)
    assert [text for text, _tone in badges] == ["PLAYING", "FAV"]
    assert ChannelRowDelegate.ROW_HEIGHT <= 70


def _standard_dialogs(host: QWidget) -> dict[str, QWidget]:
    file_dialog = QFileDialog(host, "Open M3U Playlist", "", "M3U Files (*.m3u *.m3u8)")
    file_dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    return {
        "file": file_dialog,
        "input": QInputDialog(host),
        "message": QMessageBox(QMessageBox.Icon.Question, "Remove Playlist", "Remove it?", parent=host),
    }


@pytest.mark.parametrize("mode", ["dark", "light"])
def test_standard_dialogs_paint_an_opaque_themed_background(qapp, mode):
    # The global `QWidget { background: transparent }` rule left Qt's own dialogs unpainted,
    # so the window manager showed stale pixels (a smear) while they were dragged.
    host = QWidget()
    host.setStyleSheet(Themes.get_dark_theme() if mode == "dark" else Themes.get_light_theme())
    panel = Themes.color(mode, "panel")
    try:
        for name, dialog in _standard_dialogs(host).items():
            dialog.show()
            qapp.processEvents()
            image = dialog.grab().toImage()
            pixel = image.pixelColor(image.width() - 4, image.height() // 2)
            dialog.close()
            assert pixel.alpha() == 255, f"{name} dialog background is not opaque"
            assert pixel.rgb() == panel.rgb(), f"{name} dialog background is not the panel color"
    finally:
        host.deleteLater()


@pytest.mark.parametrize("mode", ["dark", "light"])
def test_file_dialog_list_uses_theme_colors(qapp, mode):
    host = QWidget()
    host.setStyleSheet(Themes.get_dark_theme() if mode == "dark" else Themes.get_light_theme())
    try:
        dialog = _standard_dialogs(host)["file"]
        dialog.show()
        qapp.processEvents()
        view = dialog.findChild(QTreeView)
        assert view is not None
        image = view.viewport().grab().toImage()
        pixel = image.pixelColor(image.width() - 4, image.height() - 4)
        dialog.close()
        assert pixel.alpha() == 255
        assert pixel.rgb() == Themes.color(mode, "raised").rgb()
    finally:
        host.deleteLater()
