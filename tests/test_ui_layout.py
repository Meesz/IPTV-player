"""Main-screen composition: icons, empty-state action, EPG column, elided title, geometry."""

from __future__ import annotations

from datetime import datetime, timedelta
from itertools import pairwise

import pytest
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from core.models import Channel, Playlist, PlaylistReference, PlaylistSourceType, Program
from core.services.epg_service import EPGService
from core.services.favorites_service import FavoritesService
from core.services.history_service import HistoryService
from core.services.playlist_service import PlaylistService
from core.services.settings_service import SettingsService
from infra.db.epg_repository import EPGRepository
from infra.db.favorites_repository import FavoritesRepository
from infra.db.history_repository import HistoryRepository
from infra.db.playlist_repository import PlaylistRepository
from infra.db.settings_repository import SettingsRepository
from infra.db.sqlite_connection import SQLiteConnection
from infra.playback.vlc_backend import VLCBackend
from ui.controllers.epg_controller import EPGController
from ui.controllers.favorites_controller import FavoritesController
from ui.controllers.history_controller import HistoryController
from ui.controllers.main_controller import MainController
from ui.controllers.playlist_controller import PlaylistController
from ui.controllers.settings_controller import SettingsController
from ui.dialogs.playlist_manager_dialog import PlaylistManagerDialog
from ui.dialogs.xtream_source_dialog import XtreamSourceDialog
from ui.styles.icons import ICON_NAMES, make_icon
from ui.styles.themes import Themes
from ui.widgets.epg_widget import EPGWidget
from ui.widgets.left_panel import LeftPanel
from ui.widgets.notification import NotificationType, NotificationWidget
from ui.widgets.right_panel import RightPanel
from ui.windows.main_window import MainWindow

MODES = ("dark", "light")
LONG_NAME = "Sky Sports Premier League UHD 4K Ultra High Definition Feed"


@pytest.fixture
def no_vlc(monkeypatch):
    monkeypatch.setattr(VLCBackend, "initialize", classmethod(lambda cls: (False, "VLC disabled in tests")))


def _program(title: str, start: datetime, minutes: int = 30) -> Program:
    return Program(
        title=title,
        start_time=start,
        end_time=start + timedelta(minutes=minutes),
        description="",
    )


def test_icon_names_cover_the_control_set():
    assert {
        "play",
        "stop",
        "retry",
        "volume",
        "volume-muted",
        "star",
        "star-filled",
        "fullscreen",
        "copy",
        "info",
        "sources",
    } <= set(ICON_NAMES)


@pytest.mark.parametrize("mode", MODES)
def test_every_icon_renders_non_empty_in_both_themes(qapp, mode):
    color = Themes.color(mode, "text")
    for name in ICON_NAMES:
        icon = make_icon(name, color, 18)
        assert not icon.isNull(), name
        image = icon.pixmap(18, 18).toImage()
        painted = any(image.pixelColor(x, y).alpha() > 0 for x in range(image.width()) for y in range(image.height()))
        assert painted, f"{name} drew nothing"


def test_unknown_icon_name_is_rejected(qapp):
    with pytest.raises(KeyError):
        make_icon("nope", Themes.color("dark", "text"))


def test_channels_empty_state_offers_manager_action_and_emits_signal(qapp):
    panel = LeftPanel()
    stacked, state = panel._collection_views[panel.channel_list]
    requested: list[bool] = []
    panel.manage_sources_requested.connect(lambda: requested.append(True))
    panel.resize(390, 600)
    panel.show()
    qapp.processEvents()
    try:
        assert stacked.currentWidget() is state
        assert state.title_label.text() == "No playlist loaded"
        assert state.action_button.isVisible()
        assert state.action_button.text() == "Open Playlist Manager"
        state.action_button.click()
        assert requested == [True]
    finally:
        panel.close()


def test_states_without_an_action_hide_the_button(qapp):
    panel = LeftPanel()
    panel.show_loading_state("channels", "Loading playlist", "Please wait")
    _stacked, state = panel._collection_views[panel.channel_list]
    _stacked, favorites_state = panel._collection_views[panel.favorites_list]
    assert not state.action_button.isVisibleTo(panel)
    assert not favorites_state.action_button.isVisibleTo(panel)
    panel.show_loading_state("channels", "No playlist loaded", "Add one", action_label="Open Playlist Manager")
    assert state.action_button.isVisibleTo(panel)


def test_left_panel_no_longer_hosts_the_epg_widget(qapp):
    panel = LeftPanel()
    assert not hasattr(panel, "epg_widget")
    assert not hasattr(panel, "epg_status_label")


def test_epg_widget_does_not_repeat_current_program(qapp):
    widget = EPGWidget()
    widget.resize(260, 200)
    widget.show()
    now = datetime.now()
    current = _program("Evening News Special", now)
    upcoming = [_program("Late Movie", now + timedelta(minutes=30)), _program("Weather", now + timedelta(hours=1))]
    try:
        widget.set_current_program(current)
        widget.set_upcoming_programs(upcoming)
        visible_text = [widget.status_label.text()] if widget.status_label.isVisibleTo(widget) else []
        visible_text += [widget.upcoming_list.item(i).text() for i in range(widget.upcoming_list.count())]
        assert not any(current.title in text for text in visible_text)
        assert widget.upcoming_list.count() == 2
        assert "Late Movie" in widget.upcoming_list.item(0).text()
    finally:
        widget.close()


def test_epg_widget_status_messages_replace_the_list(qapp):
    widget = EPGWidget()
    widget.show()
    try:
        widget.set_loading_state("Refreshing EPG source")
        assert widget.status_label.text() == "Refreshing EPG source"
        assert widget.upcoming_list.count() == 0
        widget.set_upcoming_programs([])
        assert "No upcoming" in widget.status_label.text()
        widget.set_empty_state("Guide data ready", "Select a channel.")
        assert "Guide data ready" in widget.status_label.text()
    finally:
        widget.close()


@pytest.mark.parametrize("width", [520, 600])
def test_long_channel_title_is_elided_to_label_width(qapp, no_vlc, width):
    panel = RightPanel()
    panel.setStyleSheet(Themes.get_dark_theme())
    panel.resize(width, 700)
    panel.show()
    qapp.processEvents()
    try:
        panel.set_now_playing(Channel(name=LONG_NAME, url="http://x/y", group="Sports"), None, "Sky")
        qapp.processEvents()
        label = panel.channel_title_label
        shown = label.text()
        assert label.fontMetrics().horizontalAdvance(shown) <= label.width()
        assert label.toolTip() == LONG_NAME
        assert label.full_text() == LONG_NAME
        assert shown != LONG_NAME
        assert shown.endswith("…")
    finally:
        panel.close()


def test_icon_buttons_have_tooltip_and_accessible_name(qapp, no_vlc):
    panel = RightPanel()
    try:
        for button in (
            panel.stop_button,
            panel.retry_button,
            panel.mute_button,
            panel.favorite_button,
            panel.copy_url_button,
            panel.info_button,
            panel.fullscreen_button,
        ):
            assert button.toolTip()
            assert button.accessibleName()
            assert not button.icon().isNull()
    finally:
        panel.close()


def test_toggle_buttons_swap_icon_with_checked_state(qapp, no_vlc):
    panel = RightPanel()
    try:
        unchecked = panel.favorite_button.icon().pixmap(18, 18).toImage()
        panel.set_favorite(True)
        checked = panel.favorite_button.icon().pixmap(18, 18).toImage()
        assert unchecked != checked
        mute_before = panel.mute_button.icon().pixmap(18, 18).toImage()
        panel.set_muted(True)
        assert panel.mute_button.icon().pixmap(18, 18).toImage() != mute_before
    finally:
        panel.close()


def test_set_theme_mode_recolors_the_same_icon(qapp, no_vlc):
    panel = RightPanel()
    try:
        dark = panel.stop_button.icon().pixmap(18, 18).toImage()
        panel.set_theme_mode("light")
        light = panel.stop_button.icon().pixmap(18, 18).toImage()
        assert dark != light
    finally:
        panel.close()


def test_toggle_tooltips_reflect_state(qapp, no_vlc):
    panel = RightPanel()
    try:
        panel.set_muted(True)
        assert panel.mute_button.toolTip().startswith("Unmute")
        assert panel.mute_button.accessibleName() == "Unmute"
        panel.set_muted(False)
        assert panel.mute_button.toolTip().startswith("Mute")
        panel.set_favorite(True)
        assert panel.favorite_button.toolTip() == "Remove from favorites"
        panel.set_favorite(False)
        assert panel.favorite_button.toolTip() == "Add to favorites"
    finally:
        panel.close()


def test_source_context_without_playlist_is_not_ready_to_play(qapp, no_vlc):
    panel = RightPanel()
    try:
        panel.set_source_context("")
        assert panel.channel_title_label.full_text() == "No playlist loaded"
        assert "Sources" in panel.channel_meta_label.full_text()
        panel.set_source_context("My list")
        assert panel.channel_title_label.full_text() == "Ready to play"
    finally:
        panel.close()


def test_long_program_title_keeps_its_time_range(qapp, no_vlc):
    panel = RightPanel()
    panel.setStyleSheet(Themes.get_dark_theme())
    panel.resize(520, 700)
    panel.show()
    qapp.processEvents()
    try:
        start = datetime(2026, 1, 1, 20, 0)
        program = Program(title="A very long program title " * 6, start_time=start, end_time=start + timedelta(hours=1))
        panel.set_now_playing(Channel(name="Ch", url="http://x/y"), program, "Sky")
        qapp.processEvents()
        label = panel.program_title_label
        shown = label.text()
        assert "…" in shown
        assert shown.endswith(shown[shown.rindex(" · ") :])
        assert label.fontMetrics().horizontalAdvance(shown) <= label.width()
    finally:
        panel.close()


def test_program_description_is_clamped_to_two_lines_with_ellipsis(qapp, no_vlc):
    panel = RightPanel()
    panel.setStyleSheet(Themes.get_dark_theme())
    panel.resize(520, 700)
    panel.show()
    qapp.processEvents()
    try:
        start = datetime(2026, 1, 1, 20, 0)
        text = "Words that keep going and going across the panel. " * 20
        program = Program(title="News", start_time=start, end_time=start + timedelta(hours=1), description=text)
        panel.set_now_playing(Channel(name="Ch", url="http://x/y"), program, "Sky")
        qapp.processEvents()
        label = panel.program_description_label
        lines = label.text().split("\n")
        assert len(lines) == 2
        assert lines[-1].endswith("…")
        assert all(label.fontMetrics().horizontalAdvance(line) <= label.width() for line in lines)
        assert label.height() >= 2 * label.fontMetrics().lineSpacing()
        assert label.full_text() == text
    finally:
        panel.close()


def test_epg_widget_defaults_to_neutral_copy(qapp):
    widget = EPGWidget()
    try:
        assert "Select a channel" in widget.status_label.text()
        assert "No guide" not in widget.status_label.text()
    finally:
        widget.close()


@pytest.mark.parametrize(("width", "height"), [(600, 640), (960, 700)])
def test_right_panel_is_video_first_without_control_overlap(qapp, no_vlc, width, height):
    panel = RightPanel()
    panel.setStyleSheet(Themes.get_dark_theme())
    panel.resize(width, height)
    panel.show()
    qapp.processEvents()
    try:
        assert panel.player_surface.height() / panel.height() >= 0.55
        assert panel.now_playing_card.height() <= 190

        buttons = [b for b in panel.control_bar.findChildren(QPushButton) if b.isVisible()]
        rects = sorted((b.geometry() for b in buttons), key=lambda r: r.left())
        for left, right in pairwise(rects):
            assert left.right() < right.left(), "control bar buttons overlap"
        assert rects[-1].right() <= panel.control_bar.width()
        assert panel.control_bar.height() <= 48
        assert panel.volume_slider.minimumWidth() >= 80
        assert panel.volume_slider.maximumWidth() <= 160
    finally:
        panel.close()


def test_toast_stays_inside_its_anchor_and_off_the_control_bar(qapp, no_vlc):
    host = QWidget()
    host.resize(700, 600)
    panel = RightPanel()
    layout = QVBoxLayout(host)
    layout.addWidget(panel)
    toast = NotificationWidget(host)
    toast.set_anchor(panel.now_playing_card)
    host.show()
    qapp.processEvents()
    try:
        toast.show_message("Stream URL copied", NotificationType.SUCCESS, duration=5000)
        qapp.processEvents()
        anchor_rect = QRect(panel.now_playing_card.mapTo(host, QPoint(0, 0)), panel.now_playing_card.size())
        control_rect = QRect(panel.control_bar.mapTo(host, QPoint(0, 0)), panel.control_bar.size())
        assert toast.isVisible()
        assert anchor_rect.contains(toast.geometry())
        assert not toast.geometry().intersects(control_rect)
    finally:
        toast.timer.stop()
        host.close()


# Spec at the 70px row height: a ~400px viewport shows at least 5 full rows.
@pytest.mark.parametrize(("width", "height", "rows"), [(390, 760, 5), (340, 560, 4)])
def test_left_panel_gives_the_channel_list_the_height(qapp, width, height, rows):
    panel = LeftPanel()
    panel.setStyleSheet(Themes.get_dark_theme())
    channels = [Channel(name=f"Channel {i}", url=f"http://x/{i}", group="News") for i in range(30)]
    panel.set_channel_results(channels)
    panel.resize(width, height)
    panel.show()
    qapp.processEvents()
    try:
        view = panel.channel_list
        assert view.isVisible()
        row_height = view.sizeHintForRow(0)
        assert row_height > 0
        assert view.viewport().height() // row_height >= rows
    finally:
        panel.close()


@pytest.fixture
def make_main_window(qapp, no_vlc, tmp_path):
    windows: list[MainWindow] = []

    def factory() -> MainWindow:
        connection = SQLiteConnection(db_path=tmp_path / "app.sqlite")
        playlist_controller = PlaylistController(PlaylistService(PlaylistRepository(connection)))
        settings_controller = SettingsController(SettingsService(SettingsRepository(connection)))
        window = MainWindow(
            MainController(playlist_controller, settings_controller),
            playlist_controller,
            EPGController(EPGService(EPGRepository(connection))),
            settings_controller,
            FavoritesController(FavoritesService(FavoritesRepository(connection))),
            HistoryController(HistoryService(HistoryRepository(connection))),
        )
        windows.append(window)
        return window

    yield factory
    for window in windows:
        window.close()
        window.deleteLater()
    qapp.processEvents()


@pytest.fixture
def main_window(make_main_window):
    return make_main_window()


def test_manage_sources_request_opens_the_playlist_manager(make_main_window, monkeypatch):
    opened: list[bool] = []
    # Patch before construction: the window connects the signal to the bound method in __init__.
    monkeypatch.setattr(MainWindow, "_open_playlist_manager", lambda self: opened.append(True))
    window = make_main_window()
    window.left_panel.manage_sources_requested.emit()
    assert opened == [True]


def test_playback_chip_leaves_connecting_when_playlist_load_ends(main_window):
    chip = main_window.right_panel.playback_state_chip
    main_window._on_playlist_loading_started()
    assert chip.text() == "Connecting"

    main_window._on_playlist_loading_cancelled()

    # Loading stopped the player, so the chip must report its real (idle) state again.
    assert main_window.right_panel.player_widget.current_state == "idle"
    assert chip.text() == "Idle"


def test_playback_chip_keeps_player_detail_after_playlist_load(main_window):
    player = main_window.right_panel.player_widget
    main_window._on_playlist_loading_started()
    player._set_state("error", "Media playback failed")
    main_window._on_playlist_loading_progress("Parsing channels")

    main_window._on_playlist_loading_cancelled()

    panel = main_window.right_panel
    assert panel.playback_state_chip.text() == "Error"
    assert panel.playback_detail_label.text() == "Media playback failed"
    assert not panel.playback_detail_label.isHidden()


def test_restored_channel_playback_wins_over_chip_sync(main_window, monkeypatch):
    player = main_window.right_panel.player_widget
    # "playing" is a state the loading override never shows, so only a correctly ordered sync passes.
    monkeypatch.setattr(player, "play", lambda url, **_kwargs: player._set_state("playing", "Stream is live"))
    channel = Channel(name="News One", url="http://streams.example/news-one", group="News")
    playlist = Playlist(name="Test", channels=[channel])
    assert playlist.get_channel_by_url(channel.url) is channel
    monkeypatch.setattr(main_window, "_current_playlist", lambda: playlist)
    main_window._pending_channel_url = channel.url
    main_window._on_playlist_loading_started()
    main_window._playlist_render_active = True

    main_window._on_playlist_render_complete()

    assert main_window.right_panel.playback_state_chip.text() == "Live"
    assert player.current_state == "playing"


def test_playback_chip_returns_to_idle_after_render_without_pending_channel(main_window, monkeypatch):
    playlist = Playlist(name="Test", channels=[Channel(name="News One", url="http://streams.example/a")])
    monkeypatch.setattr(main_window, "_current_playlist", lambda: playlist)
    main_window._pending_channel_url = ""
    main_window._on_playlist_loading_started()
    main_window._playlist_render_active = True

    main_window._on_playlist_render_complete()

    assert main_window.right_panel.playback_state_chip.text() == "Idle"


def test_startup_without_playlist_shows_neutral_now_playing_copy(main_window):
    panel = main_window.right_panel
    assert panel.channel_title_label.full_text() == "No playlist loaded"
    assert "Ready to play" not in panel.channel_title_label.full_text()


def test_status_chip_ellipsis_fits_inside_the_chip(qapp, main_window):
    main_window.show()
    qapp.processEvents()
    chip = main_window.epg_status_label
    text = "EPG: " + "very long refresh progress message " * 8
    MainWindow._set_status_chip(chip, text, "warning")
    qapp.processEvents()
    shown = chip.text()
    assert shown.endswith("…")
    assert chip.toolTip() == text
    assert chip.fontMetrics().horizontalAdvance(shown) <= chip.sizeHint().width()
    assert chip.sizeHint().width() <= chip.maximumWidth()


LONG_PATH = "/media/storage/iptv/providers/" + "very-long-folder-name/" * 6 + "Sample Provider.m3u"


def _manager_with_playlist(path: str = LONG_PATH) -> PlaylistManagerDialog:
    dialog = PlaylistManagerDialog()
    dialog.set_playlists([PlaylistReference(name="Sample Provider", path=path, source_type=PlaylistSourceType.FILE)])
    return dialog


def test_playlist_manager_has_a_single_accent_button(qapp):
    dialog = _manager_with_playlist()
    accents = [b for b in dialog.findChildren(QPushButton) if b.property("accent")]
    assert accents == [dialog.select_button]
    assert dialog.select_button.text() == "Load Playlist"
    assert dialog.select_button.isEnabled()


@pytest.mark.parametrize("mode", MODES)
def test_playlist_manager_buttons_do_not_overlap(qapp, mode):
    qapp.setStyleSheet(Themes.get_dark_theme() if mode == "dark" else Themes.get_light_theme())
    try:
        dialog = _manager_with_playlist()
        dialog.show()
        qapp.processEvents()
        row = [dialog.add_button, dialog.edit_button, dialog.remove_button, dialog.test_button]
        for left, right in pairwise(row):
            assert left.geometry().right() < right.geometry().left()
        for button in (*row, dialog.select_button, dialog.cancel_button):
            assert button.width() >= button.sizeHint().width()
        assert dialog.detail_path.width() > 150
        dialog.close()
    finally:
        qapp.setStyleSheet("")


def test_playlist_manager_details_keep_the_full_long_value(qapp):
    dialog = _manager_with_playlist()
    dialog.show()
    qapp.processEvents()
    assert dialog.detail_path.text() == LONG_PATH
    assert dialog.detail_path.toolTip() == LONG_PATH
    assert dialog.detail_name.text() == "Sample Provider"
    assert dialog.details_form_host.isVisibleTo(dialog)
    assert not dialog.details_placeholder.isVisibleTo(dialog)
    dialog.close()


def test_playlist_manager_empty_selection_shows_calm_placeholder(qapp):
    dialog = PlaylistManagerDialog()
    assert dialog.details_placeholder.isVisibleTo(dialog)
    assert not dialog.details_form_host.isVisibleTo(dialog)
    assert not dialog.select_button.isEnabled()


def test_xtream_dialog_error_label_hidden_until_validation_fails(qapp):
    dialog = XtreamSourceDialog()
    assert not dialog.error_label.isVisibleTo(dialog)

    dialog.accept()
    assert dialog.error_label.isVisibleTo(dialog)
    assert "Display name" in dialog.error_label.text()

    dialog.name_input.setText("Provider")
    dialog.server_input.setText("https://provider.example")
    dialog.username_input.setText("alice")
    dialog.password_input.setText("secret")
    dialog.accept()
    assert not dialog.error_label.isVisibleTo(dialog)
    assert dialog.result() == dialog.DialogCode.Accepted


def test_xtream_dialog_primary_and_cancel_buttons(qapp):
    dialog = XtreamSourceDialog()
    buttons = {b.text(): b for b in dialog.findChildren(QPushButton)}
    assert buttons["Save Source"].property("accent")
    assert buttons["Cancel"].property("ghost")


def test_loading_overlay_card_is_compact_and_centred(qapp):
    from ui.widgets.loading_overlay import LoadingOverlay

    parent = QWidget()
    parent.resize(1200, 700)
    overlay = LoadingOverlay(parent)
    overlay.setGeometry(parent.rect())
    overlay.show_message("Loading playlist", "Loading playlist source")
    parent.show()
    qapp.processEvents()
    card = overlay.card.geometry()
    assert card.width() < 500
    assert abs(card.center().x() - overlay.rect().center().x()) <= 2
    assert abs(card.center().y() - overlay.rect().center().y()) <= 2
    parent.close()
