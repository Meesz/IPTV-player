"""Shared pytest fixtures.

PyQt6 is imported lazily inside the fixture so Qt-free test files stay Qt-free.
"""

import os
import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Point Path.home() at a temp dir so no test can touch the real ~/.simple_iptv."""
    fake_home = tmp_path / "isolated_home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    return fake_home


@pytest.fixture(autouse=True)
def no_retry_backoff_sleep(monkeypatch):
    """Playlist download retries back off; never actually wait in tests."""
    monkeypatch.setattr("core.services.playlist_service._sleep", lambda _seconds: None)


@pytest.fixture(autouse=True)
def close_leaked_widgets():
    """Close and delete top-level widgets a test left behind, so later tests start clean."""
    yield
    qt_widgets = sys.modules.get("PyQt6.QtWidgets")
    app = qt_widgets.QApplication.instance() if qt_widgets else None
    if app is None:
        return
    from PyQt6.QtCore import QEvent

    for widget in app.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


@pytest.fixture(scope="session")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
