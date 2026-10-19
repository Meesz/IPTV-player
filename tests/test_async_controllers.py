"""Async behaviour of PlaylistController and EPGController.

The thread pool is replaced by a list that captures workers; tests then drive the
workers' public signals (the same signals a real run emits) or run them synchronously.
Kills M8 (stale failure surfaced) and covers cancel/progress/finished semantics.
"""

import pytest

from core.services.epg_service import EPGService
from core.services.playlist_service import PlaylistService
from infra.db.epg_repository import EPGRepository
from infra.db.playlist_repository import PlaylistRepository
from infra.db.sqlite_connection import SQLiteConnection
from ui.controllers.epg_controller import EPGController
from ui.controllers.playlist_controller import PlaylistController


class _Harness:
    """Uniform access to the two controllers, which share the same async protocol."""

    def __init__(self, controller, load, missing_source_message):
        self.controller = controller
        self.load = load
        self.missing_source_message = missing_source_message
        self.workers: list = []
        self.errors: list[str] = []
        self.progress: list[str] = []
        self.cancelled: list[bool] = []
        self.finished: list[bool] = []
        controller.error_occurred.connect(self.errors.append)
        controller.loading_progress.connect(self.progress.append)
        controller.loading_cancelled.connect(lambda: self.cancelled.append(True))
        controller.loading_finished.connect(lambda: self.finished.append(True))


@pytest.fixture(params=["playlist", "epg"])
def harness(request, qapp, tmp_path, monkeypatch):
    connection = SQLiteConnection(db_path=tmp_path / "app.sqlite")
    if request.param == "playlist":
        controller = PlaylistController(PlaylistService(PlaylistRepository(connection)))
        built = _Harness(controller, controller.load_playlist, "Playlist file not found")
    else:
        controller = EPGController(EPGService(EPGRepository(connection)))
        built = _Harness(controller, controller.load_epg_file, "EPG file not found")
    monkeypatch.setattr(controller._thread_pool, "start", built.workers.append)
    return built


def test_stale_failure_after_newer_load_is_not_reported(harness):
    harness.load("slow-source")
    harness.load("fast-source")
    slow, fast = harness.workers

    slow.signals.failed.emit(slow.task_id, "stale failure from slow source")

    assert harness.errors == []

    fast.signals.failed.emit(fast.task_id, "active failure")
    assert harness.errors == ["active failure"]


def test_active_failure_is_reported(harness):
    harness.load("only-source")
    (worker,) = harness.workers

    worker.signals.failed.emit(worker.task_id, "boom")

    assert harness.errors == ["boom"]


def test_cancel_loading_emits_signal_and_flags_worker_cancelled(harness):
    harness.load("some-source")
    (worker,) = harness.workers
    cancel_callback = worker.kwargs["cancel_callback"]
    assert cancel_callback() is False

    harness.controller.cancel_loading(emit_signal=True)

    assert harness.cancelled == [True]
    assert cancel_callback() is True


def test_cancel_loading_without_signal_is_silent(harness):
    harness.load("some-source")
    (worker,) = harness.workers

    harness.controller.cancel_loading()

    assert harness.cancelled == []
    assert worker.kwargs["cancel_callback"]() is True


def test_cancel_loading_when_idle_does_nothing(harness):
    harness.controller.cancel_loading(emit_signal=True)

    assert harness.cancelled == []


def test_starting_a_new_load_cancels_the_previous_one(harness):
    harness.load("first")
    harness.load("second")
    first, second = harness.workers

    assert harness.cancelled == [True]
    assert first.kwargs["cancel_callback"]() is True
    assert second.kwargs["cancel_callback"]() is False


def test_stale_progress_is_not_reemitted(harness):
    harness.load("slow-source")
    harness.load("fast-source")
    slow, fast = harness.workers
    harness.progress.clear()

    slow.signals.progress.emit(slow.task_id, "stale progress")
    fast.signals.progress.emit(fast.task_id, "fresh progress")

    assert harness.progress == ["fresh progress"]


def test_finish_of_active_task_emits_loading_finished_once(harness):
    harness.load("only-source")
    (worker,) = harness.workers

    worker.signals.finished.emit(worker.task_id)
    worker.signals.finished.emit(worker.task_id)

    assert harness.finished == [True]


def test_finish_of_stale_task_does_not_emit_loading_finished(harness):
    harness.load("slow-source")
    harness.load("fast-source")
    slow, fast = harness.workers

    slow.signals.finished.emit(slow.task_id)
    assert harness.finished == []

    fast.signals.finished.emit(fast.task_id)
    assert harness.finished == [True]


def test_real_background_task_failure_reaches_controller_signals(harness, tmp_path):
    """Run the real BackgroundTask.run() synchronously; its except branch must report."""
    missing = tmp_path / "does-not-exist.m3u"
    harness.load(str(missing))
    (worker,) = harness.workers

    worker.run()

    assert len(harness.errors) == 1
    assert harness.missing_source_message in harness.errors[0]
    assert harness.finished == [True]


def test_real_background_task_success_reports_progress_and_finishes(qapp, tmp_path, monkeypatch):
    playlist_file = tmp_path / "list.m3u"
    playlist_file.write_text(
        '#EXTM3U\n#EXTINF:-1 group-title="News",News One\nhttp://example.com/one\n',
        encoding="utf-8",
    )
    controller = PlaylistController(
        PlaylistService(PlaylistRepository(SQLiteConnection(db_path=tmp_path / "a.sqlite")))
    )
    workers: list = []
    monkeypatch.setattr(controller._thread_pool, "start", workers.append)
    loaded: list = []
    errors: list[str] = []
    finished: list[bool] = []
    controller.playlist_loaded.connect(loaded.append)
    controller.error_occurred.connect(errors.append)
    controller.loading_finished.connect(lambda: finished.append(True))

    controller.load_playlist(str(playlist_file))
    workers[0].run()

    assert errors == []
    assert [channel.name for channel in loaded[0].channels] == ["News One"]
    assert controller.get_current_playlist() is loaded[0]
    assert finished == [True]
