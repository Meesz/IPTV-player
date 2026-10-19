"""The VLC render surface is childless and never painted by Qt; status text lives on a separate page."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

from infra.playback.vlc_backend import VLCBackend
from ui.widgets.player_widget import MediaEventHandler, PlayerWidget, VideoSurface

STREAM_URL = "http://provider.example/live/alice/SECRETTOKEN/101.ts"


@pytest.fixture
def player(qapp, monkeypatch):
    monkeypatch.setattr(VLCBackend, "initialize", classmethod(lambda cls: (True, "")))
    monkeypatch.setattr(VLCBackend, "get_vlc", classmethod(lambda cls: MagicMock()))
    monkeypatch.setattr(VLCBackend, "get_instance", classmethod(lambda cls: MagicMock()))
    monkeypatch.setattr(VLCBackend, "create_player", classmethod(lambda cls: MagicMock()))
    monkeypatch.setattr(VLCBackend, "bind_video_output", classmethod(lambda cls, *_args: (True, None)))
    widget = PlayerWidget()
    yield widget
    widget.reconnect_timer.stop()
    widget.deleteLater()


def _current(widget: PlayerWidget) -> QWidget:
    return widget.page_stack.currentWidget()


def test_video_surface_is_a_childless_unpainted_native_surface(player):
    surface = player.video_surface
    assert isinstance(surface, VideoSurface)
    assert surface.testAttribute(Qt.WidgetAttribute.WA_PaintOnScreen)
    assert surface.testAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
    assert surface.testAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    assert surface.paintEngine() is None
    assert surface.findChildren(QWidget) == []


def test_message_widgets_are_not_descendants_of_the_video_surface(player):
    assert not player.video_surface.isAncestorOf(player.placeholder)
    assert not player.video_surface.isAncestorOf(player.status_overlay)
    assert player.message_surface.isAncestorOf(player.placeholder)
    assert player.message_surface.isAncestorOf(player.status_overlay)


def test_initial_page_is_the_message_page(player):
    assert _current(player) is player.message_surface


def test_play_shows_message_page_even_after_video(player):
    player._on_video_output_changed(1)
    player.play(STREAM_URL)
    assert _current(player) is player.message_surface


def test_video_output_count_switches_pages_and_buffering_does_not(player):
    player.play(STREAM_URL)
    player._on_video_output_changed(1)
    assert _current(player) is player.video_surface

    player._on_media_buffering(40)
    assert _current(player) is player.video_surface

    player._on_video_output_changed(0)
    assert _current(player) is player.message_surface


@pytest.mark.parametrize("settle", ["stop", "error"])
def test_late_video_output_event_after_stop_or_error_is_ignored(player, settle):
    player.play(STREAM_URL)
    if settle == "stop":
        player.stop()
    else:
        player.current_url = None
        player._handle_playback_error("boom")

    player._on_video_output_changed(1)

    assert _current(player) is player.message_surface


def test_video_page_survives_a_fullscreen_round_trip(player):
    player.player.is_playing.return_value = True
    player.play(STREAM_URL)
    player._on_video_output_changed(1)

    assert player.toggle_fullscreen() is True
    assert _current(player) is player.video_surface
    player.toggle_fullscreen()

    assert not player.is_fullscreen
    assert _current(player) is player.video_surface


def test_media_playing_alone_does_not_show_video_page(player):
    player._on_media_playing()
    assert _current(player) is player.message_surface


def test_stop_and_error_return_to_message_page(player):
    player._on_video_output_changed(1)
    player.stop()
    assert _current(player) is player.message_surface

    player._on_video_output_changed(1)
    player.current_url = None
    player._handle_playback_error("boom")
    assert _current(player) is player.message_surface

    player._on_video_output_changed(1)
    player._on_media_stopped()
    assert _current(player) is player.message_surface


def test_shutdown_returns_to_message_page(player):
    player._on_video_output_changed(1)
    player.shutdown()
    assert _current(player) is player.message_surface


def test_refused_play_stays_on_message_page(player):
    player._embedding_available = False
    player._embedding_warning = "Embedded video needs X11"
    player._on_video_output_changed(1)
    player.play(STREAM_URL)
    assert _current(player) is player.message_surface


def test_event_handler_emits_vout_count(qapp, monkeypatch):
    monkeypatch.setattr(VLCBackend, "get_vlc", classmethod(lambda cls: MagicMock()))
    handler = MediaEventHandler(MagicMock())
    counts: list[int] = []
    handler.video_output_changed.connect(counts.append)

    handler._on_vout(SimpleNamespace(u=SimpleNamespace(new_count=1)))
    handler._on_vout(SimpleNamespace(u=SimpleNamespace(new_count=0)))
    handler._on_vout(SimpleNamespace())

    assert counts == [1, 0, 0]
