"""Diagnostic logging: handled failures and playback events reach the log without stream URLs."""

import logging
import sqlite3
import sys
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QtMsgType

from app import main as app_main
from core.errors import NetworkError, RepositoryError
from core.models import Channel
from core.redaction import RedactingFormatter
from infra.db.favorites_repository import FavoritesRepository
from infra.db.history_repository import HistoryRepository
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


class _BrokenDb:
    def get_connection(self):
        raise sqlite3.OperationalError("database is locked")


def test_repository_write_failures_do_not_log_channel_urls(caplog):
    channel = Channel(name="News One", url=SECRET_STREAM_URL, playlist_path="list.m3u")
    favorites = FavoritesRepository(_BrokenDb())
    history = HistoryRepository(_BrokenDb())

    with caplog.at_level(logging.ERROR):
        with pytest.raises(RepositoryError):
            favorites.add_favorite(channel)
        with pytest.raises(RepositoryError):
            favorites.remove_favorite(channel)
        with pytest.raises(RepositoryError):
            favorites.is_favorite(channel)
        with pytest.raises(RepositoryError):
            history.record_channel(channel, "list.m3u", 1)

    assert "News One" in caplog.text
    assert "SECRETTOKEN" not in caplog.text


def _chained_network_error_exc_info():
    try:
        try:
            raise ConnectionError("HTTPConnectionPool: /player_api.php?username=u&password=s3cret&action=x refused")
        except ConnectionError as cause:
            raise NetworkError("Could not reach provider") from cause
    except NetworkError:
        return sys.exc_info()


def test_redacting_formatter_masks_secrets_in_chained_tracebacks():
    record = logging.LogRecord(
        "test", logging.ERROR, __file__, 1, "Load failed", None, _chained_network_error_exc_info()
    )

    output = RedactingFormatter("%(levelname)s - %(message)s").format(record)

    assert "s3cret" not in output
    assert "password=***" in output
    assert "Could not reach provider" in output
    assert "ConnectionError" in output


def test_configure_logging_installs_redacting_formatter_on_all_handlers(monkeypatch):
    captured = {}
    monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: captured.update(kwargs))
    monkeypatch.setattr(app_main, "RotatingFileHandler", lambda *_a, **_k: logging.NullHandler())

    app_main.configure_logging()

    assert len(captured["handlers"]) == 2
    assert all(isinstance(h.formatter, RedactingFormatter) for h in captured["handlers"])


def test_player_without_vlc_initialises_and_ignores_controls(qapp, monkeypatch):
    monkeypatch.setattr(VLCBackend, "initialize", classmethod(lambda cls: (False, "VLC disabled in tests")))
    widget = PlayerWidget()
    try:
        assert widget.current_url is None
        widget.play(SECRET_STREAM_URL)
        widget.pause()
        widget.set_volume(50)
        assert widget.toggle_mute() is True
        assert widget.toggle_fullscreen() is False
        widget.stop()
        assert widget.retry_now() is False
        assert widget.current_state == "idle"
    finally:
        widget.reconnect_timer.stop()
        widget.deleteLater()


def test_qt_messages_are_forwarded_at_matching_level(caplog):
    with caplog.at_level(logging.DEBUG, logger="qt"):
        app_main._forward_qt_message(QtMsgType.QtWarningMsg, None, "Could not parse stylesheet")

    (record,) = caplog.records
    assert record.levelno == logging.WARNING
    assert record.getMessage() == "Could not parse stylesheet"


def test_player_masks_stream_url_echoed_in_error_message(player, caplog):
    player.current_url = SECRET_STREAM_URL
    player.max_reconnect_attempts = 0

    with caplog.at_level(logging.INFO, logger="ui.widgets.player_widget"):
        player._handle_playback_error(f"cannot open {SECRET_STREAM_URL}")

    assert "Playback error (cannot open <url>)" in caplog.text
    assert "SECRETTOKEN" not in caplog.text


def test_player_shutdown_releases_vlc_and_is_idempotent(player):
    mock_player = player.player
    player.play(SECRET_STREAM_URL)
    player.reconnect_timer.start(60_000)

    player.shutdown()

    mock_player.stop.assert_called_once()
    mock_player.release.assert_called_once()
    assert player.player is None
    assert player.current_url is None
    assert not player.reconnect_timer.isActive()

    player.shutdown()

    mock_player.release.assert_called_once()


def test_player_shutdown_exits_and_disposes_fullscreen_window(player):
    player.play(SECRET_STREAM_URL)
    player._enter_fullscreen()
    fullscreen_window = player.fullscreen_window
    assert fullscreen_window is not None and fullscreen_window.isVisible()

    player.shutdown()

    assert player.is_fullscreen is False
    assert player.fullscreen_window is None
    assert not fullscreen_window.isVisible()


def test_player_shutdown_survives_libvlc_errors_without_logging_urls(player, caplog):
    mock_player = player.player
    mock_player.stop.side_effect = RuntimeError(f"cannot stop {SECRET_STREAM_URL}")

    with caplog.at_level(logging.WARNING, logger="ui.widgets.player_widget"):
        player.shutdown()

    mock_player.release.assert_called_once()
    assert player.player is None
    assert "VLC stop failed during shutdown: RuntimeError" in caplog.text
    assert "SECRETTOKEN" not in caplog.text


def test_player_shutdown_without_vlc_does_not_raise(qapp, monkeypatch):
    monkeypatch.setattr(VLCBackend, "initialize", classmethod(lambda cls: (False, "VLC disabled in tests")))
    widget = PlayerWidget()

    widget.shutdown()
    widget.shutdown()

    assert widget.player is None
    widget.deleteLater()
