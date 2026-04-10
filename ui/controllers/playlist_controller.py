from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from pathlib import Path

from core.errors import NetworkError, ParsingError, RepositoryError, ValidationError
from core.models import Playlist, PlaylistReference
from core.services.playlist_service import PlaylistService
from ui.controllers.background_tasks import BackgroundTask, create_background_task

class PlaylistController(QObject):
    playlist_loaded = pyqtSignal(Playlist)
    error_occurred = pyqtSignal(str)
    loading_started = pyqtSignal()
    loading_progress = pyqtSignal(str)
    loading_cancelled = pyqtSignal()
    loading_finished = pyqtSignal()

    def __init__(self, service: PlaylistService):
        super().__init__()
        self.service = service
        self._thread_pool = QThreadPool.globalInstance() or QThreadPool()
        self._active_task_id: int | None = None
        self._task_sequence = 0
        self._cancelled_task_ids: set[int] = set()
        self._workers: dict[int, BackgroundTask] = {}

    def load_playlist(self, path: str, is_url: bool = False):
        self.cancel_loading(emit_signal=True)
        self._task_sequence += 1
        task_id = self._task_sequence
        self._active_task_id = task_id

        self.loading_started.emit()
        self.loading_progress.emit("Loading playlist source")
        worker = create_background_task(
            task_id,
            self.service.load_playlist,
            path,
            is_url,
            cancel_callback=lambda: not self._is_active_task(task_id),
            update_current=False,
        )
        self._workers[task_id] = worker
        worker.signals.progress.connect(self._on_task_progress)
        worker.signals.succeeded.connect(self._on_task_succeeded)
        worker.signals.failed.connect(self._on_task_failed)
        worker.signals.finished.connect(self._on_task_finished)
        self._thread_pool.start(worker)
        return True

    def get_current_playlist(self) -> Playlist | None:
        return self.service.current_playlist

    def get_channels_by_category(self, category: str):
        if self.service.current_playlist:
            if category == "All":
                return self.service.current_playlist.channels
            return self.service.current_playlist.get_channels_by_category(category)
        return []

    def search_channels(
        self,
        query: str,
        *,
        category: str = "All",
        current_category_only: bool = True,
        sort_mode: str = "name_asc",
        favorite_keys: set[tuple[str, str]] | None = None,
    ):
        return self.service.search_channels(
            query,
            category=category,
            current_category_only=current_category_only,
            sort_mode=sort_mode,
            favorite_keys=favorite_keys,
        )

    def cancel_loading(self, *, emit_signal: bool = False) -> None:
        if self._active_task_id is None:
            return
        self._cancelled_task_ids.add(self._active_task_id)
        self._active_task_id = None
        if emit_signal:
            self.loading_cancelled.emit()

    def save_playlist_reference(self, reference: PlaylistReference | str, is_url: bool | None = None) -> None:
        try:
            if isinstance(reference, str):
                if is_url is None:
                    raise ValueError("is_url must be provided when passing a path")
                reference = PlaylistReference(
                    name=Path(reference).name or "Playlist",
                    path=reference,
                    is_url=is_url,
                )
            self.service.save_playlist_reference(reference)
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    def get_saved_playlists(self):
        return self.service.get_saved_playlists()

    def get_saved_playlist(self, path: str) -> PlaylistReference | None:
        return self.service.get_saved_playlist(path)

    def remove_saved_playlist(self, path: str) -> None:
        try:
            self.service.remove_playlist_reference(path)
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    def import_playlists(
        self,
        playlists: list[PlaylistReference],
        *,
        active_playlist_path: str = "",
    ) -> bool:
        try:
            self.service.import_playlists(
                playlists,
                active_playlist_path=active_playlist_path,
            )
            return True
        except Exception as exc:
            self.error_occurred.emit(str(exc))
            return False

    def validate_playlist_reference(self, reference: PlaylistReference) -> PlaylistReference | None:
        validated, error = self.validate_playlist_reference_detailed(reference)
        if not validated and error:
            self.error_occurred.emit(error)
        return validated

    def validate_playlist_reference_detailed(
        self,
        reference: PlaylistReference,
    ) -> tuple[PlaylistReference | None, str]:
        try:
            return self.service.validate_playlist_reference(reference), ""
        except (ValidationError, RepositoryError, OSError, ValueError) as exc:
            return None, str(exc)

    def test_playlist_reference(
        self,
        reference: PlaylistReference,
        *,
        progress_callback=None,
        cancel_callback=None,
    ) -> PlaylistReference:
        return self.service.probe_playlist_reference(
            reference,
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
        )

    def update_playlist_metadata(
        self,
        path: str,
        *,
        channel_count: int,
        last_loaded_at: str,
        last_status: str,
        last_error: str = "",
    ) -> None:
        try:
            self.service.update_playlist_metadata(
                path,
                channel_count=channel_count,
                last_loaded_at=last_loaded_at,
                last_status=last_status,
                last_error=last_error,
            )
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    def _on_task_progress(self, task_id: int, message: str) -> None:
        if not self._is_active_task(task_id):
            return
        self.loading_progress.emit(message)

    def _on_task_succeeded(self, task_id: int, playlist: object) -> None:
        if not self._is_active_task(task_id):
            return
        if isinstance(playlist, Playlist):
            self.service.set_current_playlist(playlist)
            self.playlist_loaded.emit(playlist)

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
