"""Shared pytest fixtures.

PyQt6 is imported lazily inside the fixture so Qt-free test files stay Qt-free.
"""

import os

import pytest


@pytest.fixture(scope="session")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
