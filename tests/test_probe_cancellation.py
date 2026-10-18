"""Cooperative cancellation of the playlist-manager probe (offscreen Qt, fakes, no network)."""

import sys
import threading
from concurrent.futures import CancelledError

import pytest
from PyQt6.QtCore import Qt, QThreadPool

from core.models import PlaylistReference, PlaylistSourceType
from core.services.playlist_service import PlaylistService
from infra.db.playlist_repository import PlaylistRepository
from infra.db.sqlite_connection import SQLiteConnection
from infra.parsers.m3u_parser import M3UParser
from ui.controllers.playlist_controller import PlaylistController
from ui.dialogs.playlist_manager_dialog import PlaylistManagerDialog

M3U = b'#EXTM3U\n#EXTINF:-1 group-title="G",One\nhttp://example.com/one\n'


def _service(tmp_path) -> PlaylistService:
    return PlaylistService(PlaylistRepository(SQLiteConnection(db_path=tmp_path / "probe.sqlite")))


def _url_reference() -> PlaylistReference:
    return PlaylistReference(name="Remote", path="https://example.com/list.m3u", source_type=PlaylistSourceType.URL)


def test_service_probe_stops_before_download_when_already_cancelled(tmp_path, monkeypatch):
    service = _service(tmp_path)
    downloads = []
    monkeypatch.setattr(service, "_download_with_retries", lambda *a, **k: downloads.append(1) or M3U)

    with pytest.raises(CancelledError):
        service.probe_playlist_reference(_url_reference(), cancel_callback=lambda: True)

    assert downloads == []


def test_service_probe_stops_at_next_check_after_download(tmp_path, monkeypatch):
    service = _service(tmp_path)
    cancelled = {"value": False}

    def fake_download(*_args, **_kwargs):
        cancelled["value"] = True  # cancelled while the (uninterruptible) request was in flight
        return M3U

    parses = []
    monkeypatch.setattr(service, "_download_with_retries", fake_download)
    monkeypatch.setattr(M3UParser, "parse", staticmethod(lambda path: parses.append(path)))

    with pytest.raises(CancelledError):
        service.probe_playlist_reference(_url_reference(), cancel_callback=lambda: cancelled["value"])

    assert parses == []


def test_controller_probe_forwards_cancel_callback(tmp_path, qapp):
    controller = PlaylistController(_service(tmp_path))
    seen = {}

    def fake_probe(reference, *, progress_callback=None, cancel_callback=None):
        seen["cancel"] = cancel_callback
        return reference

    controller.service.probe_playlist_reference = fake_probe  # type: ignore[method-assign]
    marker = lambda: False  # noqa: E731
    controller.test_playlist_reference(_url_reference(), cancel_callback=marker)

    assert seen["cancel"] is marker


@pytest.fixture(autouse=True)
def _dispose_dialogs(monkeypatch):
    """Track dialogs created by these tests and dispose of them afterwards."""
    created: list[PlaylistManagerDialog] = []

    class TrackedDialog(PlaylistManagerDialog):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            created.append(self)

    monkeypatch.setattr(sys.modules[__name__], "PlaylistManagerDialog", TrackedDialog)
    yield
    for dialog in created:
        dialog.close()
        dialog.deleteLater()


def _dialog_with_deferred_probe(monkeypatch):
    calls = []

    def tester(ref, *, progress_callback=None, cancel_callback=None):
        calls.append(cancel_callback)
        return PlaylistReference(
            name=ref.name,
            path=ref.path,
            source_type=ref.source_type,
            xtream=ref.xtream,
            channel_count=42,
            last_status="ready",
            last_error="",
        )

    dialog = PlaylistManagerDialog()
    dialog.set_playlist_validator(lambda ref: (ref, ""))
    dialog.set_playlist_tester(tester)
    started = []
    monkeypatch.setattr(dialog._thread_pool, "start", started.append)
    dialog._add_item("Main", "https://example.com/list.m3u", True)
    dialog.playlist_list.setCurrentRow(0)
    dialog._test_selected_playlist()
    assert len(started) == 1
    return dialog, started[0], calls


def test_closing_dialog_cancels_probe_and_drops_results(qapp, monkeypatch):
    dialog, worker, calls = _dialog_with_deferred_probe(monkeypatch)
    before = dialog.playlist_list.item(0).data(Qt.ItemDataRole.UserRole)
    feedback_before = dialog.feedback_label.text()

    dialog.reject()
    worker.run()  # worker finishing late, after the dialog closed

    assert calls[0]() is True
    assert dialog.playlist_list.item(0).data(Qt.ItemDataRole.UserRole) == before
    assert dialog.playlist_list.item(0).data(Qt.ItemDataRole.UserRole).channel_count != 42
    assert dialog.feedback_label.text() == feedback_before
    assert dialog._validation_messages == {}


def test_cancel_callback_is_false_until_cancelled(qapp, monkeypatch):
    dialog, worker, calls = _dialog_with_deferred_probe(monkeypatch)
    worker.run()
    assert calls[0]() is False
    assert dialog.playlist_list.item(0).data(Qt.ItemDataRole.UserRole).channel_count == 42


def test_cancelled_probe_failure_is_not_recorded(qapp, monkeypatch):
    dialog, worker, _calls = _dialog_with_deferred_probe(monkeypatch)

    def cancelled_tester(*_args, **_kwargs):
        raise CancelledError("Playlist load cancelled")

    worker.fn = cancelled_tester
    dialog.show()  # QDialog.closeEvent only rejects a visible dialog
    dialog.close()
    assert dialog.isVisible() is False
    worker.run()

    assert dialog._validation_messages == {}
    assert "Playlist load cancelled" not in dialog.feedback_label.text()


def test_cancelling_probe_reenables_test_button(qapp, monkeypatch):
    dialog, _worker, _calls = _dialog_with_deferred_probe(monkeypatch)
    assert dialog.test_button.isEnabled() is False

    dialog._cancel_playlist_test()

    assert dialog.test_button.isEnabled() is True


def _result_for(ref, count):
    return PlaylistReference(
        name=ref.name,
        path=ref.path,
        source_type=ref.source_type,
        xtream=ref.xtream,
        channel_count=count,
        last_status="ready",
        last_error="",
    )


@pytest.mark.parametrize("late_outcome", ["success", "failure"])
def test_superseded_probe_results_and_progress_are_dropped(qapp, monkeypatch, late_outcome):
    def tester(ref, *, progress_callback=None, cancel_callback=None):
        if ref.name == "First":
            progress_callback("stale progress from A")
            if late_outcome == "failure":
                raise RuntimeError("stale failure from A")
            return _result_for(ref, 11)
        progress_callback("progress from B")
        return _result_for(ref, 22)

    dialog = PlaylistManagerDialog()
    dialog.set_playlist_validator(lambda ref: (ref, ""))
    dialog.set_playlist_tester(tester)
    started = []
    monkeypatch.setattr(dialog._thread_pool, "start", started.append)
    dialog._add_item("First", "https://example.com/first.m3u", True)
    dialog._add_item("Second", "https://example.com/second.m3u", True)

    dialog.playlist_list.setCurrentRow(0)
    dialog._test_selected_playlist()
    dialog.playlist_list.setCurrentRow(1)
    dialog._test_selected_playlist()  # supersedes probe A
    assert len(started) == 2
    worker_a, worker_b = started

    worker_b.run()
    assert dialog.feedback_label.text().startswith("Playlist verified successfully. 22")
    feedback_after_b = dialog.feedback_label.text()
    worker_a.run()  # A finishes late: progress, then result or failure

    first = dialog.playlist_list.item(0).data(Qt.ItemDataRole.UserRole)
    second = dialog.playlist_list.item(1).data(Qt.ItemDataRole.UserRole)
    assert first.channel_count != 11
    assert first.last_error == ""
    assert second.channel_count == 22
    assert dialog.feedback_label.text() == feedback_after_b
    assert list(dialog._validation_messages) == [second.source_identity]
    assert "stale" not in dialog.feedback_label.text()


def test_real_thread_pool_probe_closed_mid_flight_applies_nothing(qapp):
    release = threading.Event()
    finished = threading.Event()
    seen_cancel = []

    def tester(ref, *, progress_callback=None, cancel_callback=None):
        try:
            assert release.wait(timeout=10)
            seen_cancel.append(cancel_callback())
            progress_callback("late progress")
            if cancel_callback():
                raise CancelledError("Playlist load cancelled")
            return _result_for(ref, 42)
        finally:
            finished.set()

    pool = QThreadPool()
    dialog = PlaylistManagerDialog()
    dialog._thread_pool = pool
    dialog.set_playlist_validator(lambda ref: (ref, ""))
    dialog.set_playlist_tester(tester)
    dialog._add_item("Main", "https://example.com/list.m3u", True)
    dialog.playlist_list.setCurrentRow(0)
    dialog.show()
    dialog._test_selected_playlist()
    before = dialog.playlist_list.item(0).data(Qt.ItemDataRole.UserRole)

    dialog.reject()
    release.set()
    try:
        assert finished.wait(timeout=10)
        assert pool.waitForDone(10000)
        qapp.processEvents()
    finally:
        release.set()

    assert seen_cancel == [True]
    assert dialog.playlist_list.item(0).data(Qt.ItemDataRole.UserRole) == before
    assert dialog._validation_messages == {}
    assert "late progress" not in dialog.feedback_label.text()
    assert "cancelled" not in dialog.feedback_label.text()
