"""Diagnostic logging: handled failures and playback events reach the log without stream URLs."""

import logging
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QtMsgType

from app import main as app_main
from core.models import Channel
from infra.playback.vlc_backend import VLCBackend
from ui.controllers.background_tasks import BackgroundTask
from ui.controllers.favorites_controller import FavoritesController
from ui.widgets.player_widget import PlayerWidget

SECRET_STREAM_URL = "http://provider.example/live/alice/SECRETTOKEN/101.ts"


class _FailingFavoritesService:
    def add_favorite(self, channel):
        raise RuntimeError("database is locked")


@pytest.fixture
def player(qapp, monkeypatch):
    """A PlayerWidget wired to mock VLC objects, so no libvlc is needed."""
    monkeypatch.setattr(VLCBackend, "initialize", classmethod(lambda cls: (True, "")))
    monkeypatch.setattr(VLCBackend, "get_vlc", classmethod(lambda cls: MagicMock()))
    monkeypatch.setattr(VLCBackend, "get_instance", classmethod(lambda cls: MagicMock()))
    monkeypatch.setattr(VLCBackend, "create_player", classmethod(lambda cls: MagicMock()))
    monkeypatch.setattr(VLCBackend, "bind_video_output", classmethod(lambda cls, *_args: ""))
    widget = PlayerWidget()
    yield widget
    widget.reconnect_timer.stop()
    widget.deleteLater()


def test_background_task_failure_is_logged_with_traceback(qapp, caplog):
    def explode(*, progress_callback):
        raise RuntimeError("boom")

    failures: list[str] = []
    task = BackgroundTask(7, explode)
    task.signals.failed.connect(lambda _task_id, message: failures.append(message))

    with caplog.at_level(logging.ERROR, logger="ui.controllers.background_tasks"):
        task.run()

    assert failures == ["boom"]
    (record,) = caplog.records
    assert "Background task 7 (explode) failed" in record.getMessage()
    assert record.exc_info is not None


def test_controller_error_shown_to_user_is_also_logged(qapp, caplog):
    controller = FavoritesController(_FailingFavoritesService())  # type: ignore[arg-type]
    errors: list[str] = []
    controller.error_occurred.connect(errors.append)
    channel = Channel(name="News One", url=SECRET_STREAM_URL, group="News")

    with caplog.at_level(logging.ERROR, logger="ui.controllers.favorites_controller"):
        assert controller.add_favorite(channel) is False

    assert errors == ["database is locked"]
    (record,) = caplog.records
    assert "News One" in record.getMessage()
    assert record.exc_info is not None
    assert "SECRETTOKEN" not in caplog.text


def test_player_logs_state_transitions_once(player, caplog):
    with caplog.at_level(logging.INFO, logger="ui.widgets.player_widget"):
        player._set_state("buffering", "Buffering 10%")
        player._set_state("buffering", "Buffering 50%")
        player._set_state("playing", "Stream is live")

    messages = [record.getMessage() for record in caplog.records]
    assert messages == [
        "Playback state idle -> buffering (Buffering 10%)",
        "Playback state buffering -> playing (Stream is live)",
    ]


def test_player_logs_reconnects_and_final_error_without_stream_url(player, caplog):
    player.current_url = SECRET_STREAM_URL
    player.max_reconnect_attempts = 1

    with caplog.at_level(logging.INFO, logger="ui.widgets.player_widget"):
        player._handle_playback_error("Media playback failed")
        player._handle_playback_error("Media playback failed")

    assert "reconnect attempt 1/1 in 2s" in caplog.text
    assert "giving up after 1 reconnect attempts" in caplog.text
    assert "SECRETTOKEN" not in caplog.text


def test_qt_messages_are_forwarded_at_matching_level(caplog):
    with caplog.at_level(logging.DEBUG, logger="qt"):
        app_main._forward_qt_message(QtMsgType.QtWarningMsg, None, "Could not parse stylesheet")

    (record,) = caplog.records
    assert record.levelno == logging.WARNING
    assert record.getMessage() == "Could not parse stylesheet"
