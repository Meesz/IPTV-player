"""Video embedding: Qt platform selection and refusing playback that VLC would open in its own window."""

from unittest.mock import MagicMock

import pytest

from app.main import prefer_xcb_on_wayland
from infra.playback import vlc_backend
from infra.playback.vlc_backend import VLCBackend
from ui.widgets.player_widget import PlayerWidget

STREAM_URL = "http://provider.example/live/alice/SECRETTOKEN/101.ts"


def test_prefer_xcb_sets_platform_on_wayland_with_display():
    env = {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":1"}
    assert prefer_xcb_on_wayland(env, "linux") is True
    assert env["QT_QPA_PLATFORM"] == "xcb;wayland"


def test_prefer_xcb_detects_wayland_from_session_type():
    env = {"XDG_SESSION_TYPE": "Wayland", "DISPLAY": ":0"}
    assert prefer_xcb_on_wayland(env, "linux") is True
    assert env["QT_QPA_PLATFORM"] == "xcb;wayland"


@pytest.mark.parametrize(
    ("env", "platform"),
    [
        ({"QT_QPA_PLATFORM": "wayland", "WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":1"}, "linux"),
        ({"QT_QPA_PLATFORM": "offscreen", "WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":1"}, "linux"),
        ({"WAYLAND_DISPLAY": "wayland-0"}, "linux"),
        ({"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": " "}, "linux"),
        ({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"}, "linux"),
        ({"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":1"}, "win32"),
        ({"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":1"}, "darwin"),
    ],
)
def test_prefer_xcb_is_a_no_op_otherwise(env, platform):
    before = dict(env)
    assert prefer_xcb_on_wayland(env, platform) is False
    assert env == before


@pytest.fixture
def linux(monkeypatch):
    monkeypatch.setattr(vlc_backend.sys, "platform", "linux")
    monkeypatch.setenv("DISPLAY", ":1")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")


def test_bind_on_xcb_sets_xwindow(linux):
    player = MagicMock()
    embedded, message = VLCBackend.bind_video_output(player, 42, "xcb")
    assert embedded is True
    assert "XWayland" in (message or "")
    player.set_xwindow.assert_called_once_with(42)


@pytest.mark.parametrize("qt_platform", ["wayland", "offscreen", ""])
def test_bind_on_other_qt_platforms_refuses_without_touching_player(linux, qt_platform):
    player = MagicMock()
    embedded, message = VLCBackend.bind_video_output(player, 42, qt_platform)
    assert embedded is False
    assert "QT_QPA_PLATFORM=xcb" in (message or "")
    player.set_xwindow.assert_not_called()


def test_bind_without_xwayland_does_not_suggest_xcb_restart(linux, monkeypatch):
    monkeypatch.delenv("DISPLAY")
    embedded, message = VLCBackend.bind_video_output(MagicMock(), 42, "wayland")
    assert embedded is False
    assert "XWayland" in (message or "")
    assert "DISPLAY" in (message or "")
    assert "QT_QPA_PLATFORM=xcb" not in (message or "")


def test_bind_refusal_with_display_mentions_xcb_plugin(linux):
    _embedded, message = VLCBackend.bind_video_output(MagicMock(), 42, "wayland")
    assert "libxcb-cursor" in (message or "")


@pytest.fixture
def make_player(qapp, monkeypatch):
    created: list[PlayerWidget] = []

    def build(bind_result=None):
        """Mock VLC; `bind_result=None` keeps the real `bind_video_output`."""
        vlc_player = MagicMock()
        instance = MagicMock()
        monkeypatch.setattr(VLCBackend, "initialize", classmethod(lambda cls: (True, "")))
        monkeypatch.setattr(VLCBackend, "get_vlc", classmethod(lambda cls: MagicMock()))
        monkeypatch.setattr(VLCBackend, "get_instance", classmethod(lambda cls: instance))
        monkeypatch.setattr(VLCBackend, "create_player", classmethod(lambda cls: vlc_player))
        if bind_result is not None:
            monkeypatch.setattr(VLCBackend, "bind_video_output", classmethod(lambda cls, *_args: bind_result))
        widget = PlayerWidget()
        created.append(widget)
        return widget, vlc_player, instance

    yield build
    for widget in created:
        widget.reconnect_timer.stop()
        widget.deleteLater()


def test_play_is_refused_when_embedding_is_unavailable(make_player):
    widget, vlc_player, instance = make_player((False, "Embedded video needs X11"))
    states: list[tuple[str, str]] = []
    widget.playback_state_changed.connect(lambda state, detail: states.append((state, detail)))

    widget.play(STREAM_URL)

    vlc_player.play.assert_not_called()
    vlc_player.set_media.assert_not_called()
    instance.media_new.assert_not_called()
    assert states == [("error", "Embedded video needs X11")]
    assert widget.current_state == "error"
    assert widget.placeholder.text() == "Embedded video needs X11"
    assert not widget.reconnect_timer.isActive()
    assert "SECRETTOKEN" not in widget.placeholder.text()


def test_play_proceeds_when_embedding_is_available(make_player):
    widget, vlc_player, _instance = make_player((True, None))

    widget.play(STREAM_URL)

    vlc_player.play.assert_called_once()
    assert widget.current_state == "connecting"


def test_real_binding_under_offscreen_refuses_play(make_player, linux):
    # The qapp fixture runs the offscreen Qt platform, so this proves the widget passes the
    # effective platform name through to the real bind_video_output.
    widget, vlc_player, instance = make_player()

    widget.play(STREAM_URL)

    assert widget.current_state == "error"
    assert "offscreen" in widget.placeholder.text()
    assert "SECRETTOKEN" not in widget.placeholder.text()
    vlc_player.set_xwindow.assert_not_called()
    vlc_player.set_media.assert_not_called()
    vlc_player.play.assert_not_called()
    instance.media_new.assert_not_called()
    assert not widget.reconnect_timer.isActive()


def test_bind_outcome_is_logged_once_per_change(make_player, caplog):
    with caplog.at_level("INFO", logger="ui.widgets.player_widget"):
        widget, _vlc_player, _instance = make_player((False, "Embedded video needs X11"))
        widget._setup_player()
        widget._setup_player()

    refusals = [r for r in caplog.records if "Video embedding unavailable" in r.getMessage()]
    assert len(refusals) == 1
