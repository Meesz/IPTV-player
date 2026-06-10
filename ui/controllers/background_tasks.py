from __future__ import annotations

from typing import Any, Callable

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal


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
        except Exception as exc:  # pragma: no cover - exercised via controller tests
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
