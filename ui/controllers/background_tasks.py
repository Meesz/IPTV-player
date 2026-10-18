from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

logger = logging.getLogger(__name__)


class BackgroundTaskSignals(QObject):
    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)
    finished = pyqtSignal(int)


class BackgroundTask(QRunnable):
    def __init__(
        self,
        task_id: int,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self.task_id = task_id
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = BackgroundTaskSignals()

    def run(self) -> None:
        try:
            result = self.fn(
                *self.args,
                progress_callback=lambda message: self.signals.progress.emit(self.task_id, message),
                **self.kwargs,
            )
            self.signals.succeeded.emit(self.task_id, result)
        except Exception as exc:
            logger.exception("Background task %s (%s) failed", self.task_id, getattr(self.fn, "__name__", self.fn))
            self.signals.failed.emit(self.task_id, str(exc))
        finally:
            self.signals.finished.emit(self.task_id)


def create_background_task(
    task_id: int,
    fn: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> BackgroundTask:
    return BackgroundTask(task_id, fn, *args, **kwargs)
