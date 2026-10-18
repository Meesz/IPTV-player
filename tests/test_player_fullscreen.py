"""Fullscreen enter/exit must return the player to its original layout slot and size."""

from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

from infra.playback.vlc_backend import VLCBackend
from ui.widgets.player_widget import PlayerWidget


@pytest.fixture
def hosted_player(qapp, monkeypatch):
    vlc_player = MagicMock()
    vlc_player.is_playing.return_value = True
    monkeypatch.setattr(VLCBackend, "initialize", classmethod(lambda cls: (True, "")))
    monkeypatch.setattr(VLCBackend, "get_vlc", classmethod(lambda cls: MagicMock()))
    monkeypatch.setattr(VLCBackend, "get_instance", classmethod(lambda cls: MagicMock()))
    monkeypatch.setattr(VLCBackend, "create_player", classmethod(lambda cls: vlc_player))
    monkeypatch.setattr(VLCBackend, "bind_video_output", classmethod(lambda cls, *_args: (True, None)))

    # Mirrors RightPanel: the player is the only item in its surface's layout, so removing it for
    # fullscreen leaves that layout empty.
    window = QFrame()
    window.resize(1000, 700)
    window_layout = QVBoxLayout(window)
    host = QFrame()
    host_layout = QVBoxLayout(host)
    widget = PlayerWidget()
    host_layout.addWidget(widget, stretch=1)
    window_layout.addWidget(host, stretch=1)
    window_layout.addWidget(QLabel("controls"))
    window.show()
    qapp.processEvents()
    yield host, host_layout, widget
    widget.shutdown()
    window.close()
    window.deleteLater()


@pytest.mark.parametrize("exit_via", ["toggle", "window_close"])
def test_exiting_fullscreen_restores_layout_slot_and_size(qapp, hosted_player, exit_via):
    host, host_layout, widget = hosted_player
    normal_geometry = widget.geometry()

    assert widget.toggle_fullscreen() is True
    assert widget.is_fullscreen
    if exit_via == "toggle":
        widget.toggle_fullscreen()
    else:
        widget.fullscreen_window.close()
    qapp.processEvents()

    assert not widget.is_fullscreen
    assert widget.parent() is host
    assert host_layout.indexOf(widget) == 0
    assert host_layout.stretch(0) == 1
    assert widget.geometry() == normal_geometry


def test_repeated_fullscreen_round_trips_keep_the_slot(qapp, hosted_player):
    _host, host_layout, widget = hosted_player
    normal_geometry = widget.geometry()

    for _ in range(3):
        widget.toggle_fullscreen()
        widget.toggle_fullscreen()
        qapp.processEvents()

    assert host_layout.indexOf(widget) == 0
    assert host_layout.count() == 1
    assert widget.geometry() == normal_geometry
