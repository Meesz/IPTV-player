from typing import List

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from core.errors import NetworkError, ParsingError, RepositoryError
from core.models import ParseWarning, Program
from core.services.epg_service import EPGService
from ui.controllers.background_tasks import BackgroundTask, create_background_task


class EPGController(QObject):
    epg_loaded = pyqtSignal()
    error_occurred = pyqtSignal(str)
    loading_started = pyqtSignal()
    loading_progress = pyqtSignal(str)
    loading_cancelled = pyqtSignal()
    loading_finished = pyqtSignal()

    def __init__(self, service: EPGService):
        super().__init__()
        self.service = service
        self._thread_pool = QThreadPool.globalInstance() or QThreadPool()
        self._active_task_id: int | None = None
        self._task_sequence = 0
        self._cancelled_task_ids: set[int] = set()
        self._workers: dict[int, BackgroundTask] = {}
        self._last_loaded_source = ""
        self._last_loaded_is_url = False
        self._last_warnings: list[ParseWarning] = []

    def load_epg_file(self, path: str) -> bool:
        return self._start_load(self.service.load_epg_from_path, path, is_url=False)

    def load_epg_url(self, url: str) -> bool:
        return self._start_load(self.service.load_epg_from_url, url, is_url=True)

    def get_current_program(self, channel_id: str) -> Program | None:
        if not channel_id:
            return None
        return self.service.get_program_for_channel(channel_id)

    def get_upcoming_programs(self, channel_id: str) -> List[Program]:
        if not channel_id:
            return []
        return self.service.get_upcoming_programs(channel_id)

    @property
    def loaded_channel_count(self) -> int:
        return len(self.service.loaded_channels)

    @property
    def last_loaded_source(self) -> str:
        return self._last_loaded_source

    @property
    def last_loaded_is_url(self) -> bool:
        return self._last_loaded_is_url

    @property
    def last_warnings(self) -> list[ParseWarning]:
        return list(self._last_warnings)

    def cancel_loading(self, *, emit_signal: bool = False) -> None:
        if self._active_task_id is None:
            return
        self._cancelled_task_ids.add(self._active_task_id)
        self._active_task_id = None
        if emit_signal:
            self.loading_cancelled.emit()

    def _start_load(self, loader, source: str, *, is_url: bool) -> bool:
        self.cancel_loading(emit_signal=True)
        self._task_sequence += 1
        task_id = self._task_sequence
        self._active_task_id = task_id
        self._last_loaded_source = source
        self._last_loaded_is_url = is_url
        self._last_warnings = []

        self.loading_started.emit()
        self.loading_progress.emit("Loading EPG source")
        worker = create_background_task(
            task_id,
            loader,
            source,
            cancel_callback=lambda: not self._is_active_task(task_id),
        )
        self._workers[task_id] = worker
        worker.signals.progress.connect(self._on_task_progress)
        worker.signals.succeeded.connect(self._on_task_succeeded)
        worker.signals.failed.connect(self._on_task_failed)
        worker.signals.finished.connect(self._on_task_finished)
        self._thread_pool.start(worker)
        return True

    def _on_task_progress(self, task_id: int, message: str) -> None:
        if not self._is_active_task(task_id):
            return
        self.loading_progress.emit(message)

    def _on_task_succeeded(self, task_id: int, _result: object) -> None:
        if not self._is_active_task(task_id):
            return
        self._last_warnings = self.service.last_warnings
        self.epg_loaded.emit()

    def _on_task_failed(self, task_id: int, message: str) -> None:
        if not self._is_active_task(task_id):
            return
        self.error_occurred.emit(message)

    def _on_task_finished(self, task_id: int) -> None:
        self._workers.pop(task_id, None)
        if self._active_task_id == task_id:
            self._active_task_id = None
            self.loading_finished.emit()
        self._cancelled_task_ids.discard(task_id)

    def _is_active_task(self, task_id: int) -> bool:
        return task_id == self._active_task_id and task_id not in self._cancelled_task_ids
