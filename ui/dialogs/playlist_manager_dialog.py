from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import replace

from PyQt6.QtCore import QSize, Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOption,
    QVBoxLayout,
    QWidget,
)

from core.models import PlaylistReference, PlaylistSourceType
from ui.controllers.background_tasks import BackgroundTask, create_background_task
from ui.dialogs.xtream_source_dialog import XtreamSourceDialog


class _DetailValue(QLabel):
    """Read-only detail value. ``text()`` is always the full value, also exposed as tooltip.

    With ``elide=True`` the value stays on one line and is elided at paint time; otherwise it wraps.
    """

    def __init__(self, elide: bool = False) -> None:
        super().__init__("")
        self.setObjectName("playlist_detail_value")
        self._elide = elide
        self.setWordWrap(not elide)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

    def setText(self, text: str | None) -> None:
        super().setText(text)
        self.setToolTip(text or "")

    def minimumSizeHint(self) -> QSize:
        return QSize(0, super().minimumSizeHint().height())

    def paintEvent(self, event) -> None:
        if not self._elide:
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setPen(self.palette().windowText().color())
        shown = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideMiddle, self.width())
        painter.drawText(self.rect(), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), shown)


class PlaylistManagerDialog(QDialog):
    """Dialog for adding, editing, and selecting playlist references."""

    playlist_selected = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("playlist_dialog")
        self.setWindowTitle("Playlist Manager")
        self.setMinimumSize(880, 520)
        self.resize(960, 580)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._active_playlist_path = ""
        self._playlist_validator: Callable[[PlaylistReference], tuple[PlaylistReference | None, str]] | None = None
        self._playlist_tester: Callable[..., PlaylistReference] | None = None
        self._thread_pool = QThreadPool.globalInstance() or QThreadPool()
        self._tester_task_id = 0
        self._tester_worker: BackgroundTask | None = None
        self._tester_identity: str | None = None
        self._validation_messages: dict[str, tuple[str, str]] = {}
        self._init_ui()

    def paintEvent(self, event) -> None:
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

    def _init_ui(self) -> None:  # noqa: PLR0915  (Qt UI builder; pre-existing size)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 20)
        root_layout.setSpacing(4)

        title = QLabel("Playlists")
        title.setObjectName("dialog_title")
        root_layout.addWidget(title)

        subtitle = QLabel("Saved sources for live TV. Pick one to load it into the player.")
        subtitle.setObjectName("dialog_subtitle")
        root_layout.addWidget(subtitle)

        self.feedback_label = QLabel("Ready.")
        self.feedback_label.setObjectName("playlist_feedback")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setProperty("stateTone", "ready")
        root_layout.addSpacing(6)
        root_layout.addWidget(self.feedback_label)
        root_layout.addSpacing(10)

        body = QHBoxLayout()
        body.setSpacing(16)

        list_layout = QVBoxLayout()
        list_layout.setSpacing(8)

        self.header = QLabel("SAVED PLAYLISTS")
        self.header.setObjectName("panel_heading")
        list_layout.addWidget(self.header)

        self.playlist_list = QListWidget()
        self.playlist_list.setObjectName("playlist_list")
        self.playlist_list.itemSelectionChanged.connect(self._selection_changed)
        self.playlist_list.itemDoubleClicked.connect(self._edit_playlist)
        self.playlist_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.playlist_list.customContextMenuRequested.connect(self._show_context_menu)
        list_layout.addWidget(self.playlist_list, stretch=1)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)

        self.add_button = QPushButton("Add")
        self.add_button.setObjectName("playlist_add_button")
        self.add_menu = QMenu(self)
        self.add_menu.addAction("From File...", self._add_playlist_file)
        self.add_menu.addAction("From URL...", self._add_playlist_url)
        self.add_menu.addAction("From Xtream Codes...", self._add_playlist_xtream)
        self.add_button.setMenu(self.add_menu)

        self.edit_button = QPushButton("Edit")
        self.edit_button.setEnabled(False)
        self.remove_button = QPushButton("Remove")
        self.remove_button.setEnabled(False)
        self.test_button = QPushButton("Test Source")
        self.test_button.setEnabled(False)
        self.select_button = QPushButton("Load Playlist")
        self.select_button.setProperty("accent", True)
        self.select_button.setDefault(True)
        self.select_button.setEnabled(False)

        self.edit_button.clicked.connect(self._edit_playlist)
        self.remove_button.clicked.connect(self._remove_playlist)
        self.test_button.clicked.connect(self._test_selected_playlist)
        self.select_button.clicked.connect(self._select_playlist)

        for button in (self.add_button, self.edit_button, self.remove_button, self.test_button):
            button.setProperty("ghost", True)
            button_row.addWidget(button)
        button_row.addStretch()

        list_layout.addLayout(button_row)
        body.addLayout(list_layout, stretch=5)

        self.details_card = QFrame()
        self.details_card.setObjectName("playlist_detail_card")
        self.details_card.setMinimumWidth(320)
        details_outer = QVBoxLayout(self.details_card)
        details_outer.setContentsMargins(20, 18, 20, 18)
        details_outer.setSpacing(12)

        details_heading = QLabel("DETAILS")
        details_heading.setObjectName("panel_heading")
        details_outer.addWidget(details_heading)

        self.details_placeholder = QLabel("Select a playlist to see its source, status and last test result.")
        self.details_placeholder.setObjectName("placeholder_hint")
        self.details_placeholder.setWordWrap(True)
        self.details_placeholder.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        details_outer.addWidget(self.details_placeholder)

        self.details_form_host = QWidget()
        form = QFormLayout(self.details_form_host)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.detail_name = _DetailValue(elide=True)
        self.detail_source = _DetailValue()
        self.detail_path = _DetailValue(elide=True)
        self.detail_channels = _DetailValue()
        self.detail_loaded = _DetailValue()
        self.detail_status = _DetailValue()
        self.detail_validation = _DetailValue()

        for caption, value in (
            ("NAME", self.detail_name),
            ("SOURCE", self.detail_source),
            ("PATH", self.detail_path),
            ("CHANNELS", self.detail_channels),
            ("LAST LOADED", self.detail_loaded),
            ("STATUS", self.detail_status),
            ("VALIDATION", self.detail_validation),
        ):
            caption_label = QLabel(caption)
            caption_label.setObjectName("panel_heading")
            form.addRow(caption_label, value)

        details_outer.addWidget(self.details_form_host)
        details_outer.addStretch()

        body.addWidget(self.details_card, stretch=4)
        root_layout.addLayout(body, stretch=1)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 16, 0, 0)
        footer.setSpacing(8)
        footer.addStretch()
        self.cancel_button = QPushButton("Close")
        self.cancel_button.setProperty("ghost", True)
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.clicked.connect(self.reject)
        footer.addWidget(self.cancel_button)
        footer.addWidget(self.select_button)
        root_layout.addLayout(footer)

        self._set_details(None)

    def _selection_changed(self) -> None:
        has_selection = bool(self.playlist_list.selectedItems())
        self.remove_button.setEnabled(has_selection)
        self.select_button.setEnabled(has_selection)
        self.edit_button.setEnabled(has_selection)
        self.test_button.setEnabled(has_selection and self._tester_worker is None)

        item = self.playlist_list.currentItem()
        data = item.data(Qt.ItemDataRole.UserRole) if item else None
        self._set_details(data if isinstance(data, PlaylistReference) else None)

    def _add_playlist_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Open M3U Playlist", "", "M3U Files (*.m3u *.m3u8)")
        if file_path:
            self._add_playlist_entry(file_path, is_url=False)

    def _add_playlist_url(self) -> None:
        url, ok = QInputDialog.getText(self, "Add Playlist URL", "Enter the M3U playlist URL:")
        if ok and url:
            self._add_playlist_entry(url.strip(), is_url=True)

    def _add_playlist_xtream(self) -> None:
        dialog = XtreamSourceDialog(self)
        if dialog.exec():
            playlist = self._validated_playlist(dialog.to_reference())
            if not playlist or self._has_duplicate(playlist):
                return
            self._add_playlist_item(playlist)
            self._set_feedback(
                "ready",
                "Xtream source added to the library. Use Test Source to verify the credentials.",
            )

    def _add_playlist_entry(self, path: str, is_url: bool = False) -> None:
        default_name = os.path.basename(path) if not is_url else "URL Playlist"
        name, ok = QInputDialog.getText(
            self,
            "Playlist Name",
            "Enter a name for this playlist:",
            text=default_name,
        )
        if not ok or not name:
            return
        self._add_item(name.strip(), path, is_url)

    def _add_item(self, name: str, path: str, is_url: bool) -> None:
        playlist = self._validated_playlist(
            PlaylistReference(
                name=name,
                path=path,
                source_type=PlaylistSourceType.URL if is_url else PlaylistSourceType.FILE,
            )
        )
        if not playlist or self._has_duplicate(playlist):
            return
        self._add_playlist_item(playlist)
        self._set_feedback("ready", "Playlist added to the library. Use Test Source to verify it.")

    def _add_playlist_item(self, playlist: PlaylistReference) -> None:
        item = QListWidgetItem(self._item_title(playlist))
        item.setData(Qt.ItemDataRole.UserRole, playlist)
        self.playlist_list.addItem(item)

    def _remove_playlist(self) -> None:
        current_item = self.playlist_list.currentItem()
        if not current_item:
            return
        playlist = current_item.data(Qt.ItemDataRole.UserRole)
        if isinstance(playlist, PlaylistReference) and playlist.source_identity == self._active_playlist_path:
            self._show_warning("The active playlist cannot be removed.")
            return
        confirm = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Remove '{playlist.name if isinstance(playlist, PlaylistReference) else current_item.text()}' "
            "from the library?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.playlist_list.takeItem(self.playlist_list.row(current_item))
            self._set_feedback("warning", "Playlist removed from the library.")
            self._set_details(None)

    def _select_playlist(self) -> None:
        current_item = self.playlist_list.currentItem()
        if not current_item:
            return
        playlist = current_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(playlist, PlaylistReference):
            return
        self.playlist_selected.emit(playlist)
        self.accept()

    def _edit_playlist(self) -> None:  # noqa: PLR0911, PLR0912  (validation branches; pre-existing)
        current_item = self.playlist_list.currentItem()
        if not current_item:
            return

        data = current_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, PlaylistReference):
            return
        name, ok = QInputDialog.getText(self, "Edit Playlist Name", "Enter new name:", text=data.name)
        if not ok or not name:
            return

        if data.source_type == PlaylistSourceType.XTREAM:
            xtream_reference = PlaylistReference(
                name=name.strip(),
                path="",
                source_type=PlaylistSourceType.XTREAM,
                xtream=data.xtream,
                channel_count=data.channel_count,
                last_loaded_at=data.last_loaded_at,
                last_status=data.last_status,
                last_error=data.last_error,
            )
            dialog = XtreamSourceDialog(self, xtream_reference)
            if not dialog.exec():
                return
            playlist = self._validated_playlist(dialog.to_reference())
            if not playlist:
                return
            if data.source_identity == self._active_playlist_path and playlist.identity_key() != data.identity_key():
                self._show_warning("The active playlist source cannot be changed while it is active.")
                return
            if self._has_duplicate(playlist, ignore_item=current_item):
                return
            current_item.setData(Qt.ItemDataRole.UserRole, playlist)
            current_item.setText(self._item_title(playlist))
            self._set_feedback("ready", "Playlist updated.")
            self._set_details(playlist)
            return

        path = data.path
        is_url = data.source_type == PlaylistSourceType.URL
        if is_url:
            new_path, ok = QInputDialog.getText(
                self,
                "Edit Playlist URL",
                "Enter new URL:",
                text=path,
            )
            if not ok or not new_path:
                return
            if data.source_identity == self._active_playlist_path and new_path.strip() != data.path:
                self._show_warning("The active playlist source cannot be changed while it is active.")
                return
            path = new_path.strip()
        else:
            new_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select New Playlist File",
                path,
                "M3U Files (*.m3u *.m3u8)",
            )
            if new_path:
                if data.source_identity == self._active_playlist_path and new_path != data.path:
                    self._show_warning("The active playlist source cannot be changed while it is active.")
                    return
                path = new_path

        playlist = self._validated_playlist(
            PlaylistReference(
                name=name.strip(),
                path=path,
                source_type=PlaylistSourceType.URL if is_url else PlaylistSourceType.FILE,
                channel_count=data.channel_count,
                last_loaded_at=data.last_loaded_at,
                last_status=data.last_status,
                last_error=data.last_error,
            )
        )
        if not playlist:
            return
        if self._has_duplicate(playlist, ignore_item=current_item):
            return

        current_item.setData(Qt.ItemDataRole.UserRole, playlist)
        current_item.setText(self._item_title(playlist))
        self._set_feedback("ready", "Playlist updated.")
        self._set_details(playlist)

    def _show_context_menu(self, position) -> None:
        item = self.playlist_list.itemAt(position)
        if not item:
            return
        menu = QMenu()
        edit_action = menu.addAction("Edit")
        test_action = menu.addAction("Test Source")
        remove_action = menu.addAction("Remove")
        action = menu.exec(self.playlist_list.mapToGlobal(position))
        if action == edit_action:
            self._edit_playlist()
        elif action == test_action:
            self._test_selected_playlist()
        elif action == remove_action:
            self._remove_playlist()

    def get_playlists(self) -> list[PlaylistReference]:
        playlists: list[PlaylistReference] = []
        for index in range(self.playlist_list.count()):
            item = self.playlist_list.item(index)
            data = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(data, PlaylistReference):
                continue
            playlists.append(
                PlaylistReference(
                    name=data.name,
                    path=data.path,
                    source_type=data.source_type,
                    xtream=data.xtream,
                    channel_count=data.channel_count,
                    last_loaded_at=data.last_loaded_at,
                    last_status=data.last_status,
                    last_error=data.last_error,
                )
            )
        return playlists

    def set_playlists(self, playlists: Sequence[PlaylistReference]) -> None:
        self.playlist_list.clear()
        for playlist in playlists:
            self._add_playlist_item(playlist)
        if self.playlist_list.count():
            self.playlist_list.setCurrentRow(0)

    def set_active_playlist(self, path: str) -> None:
        self._active_playlist_path = path
        for index in range(self.playlist_list.count()):
            item = self.playlist_list.item(index)
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, PlaylistReference):
                item.setText(self._item_title(data))

    def set_playlist_validator(
        self,
        validator: Callable[[PlaylistReference], tuple[PlaylistReference | None, str]],
    ) -> None:
        self._playlist_validator = validator

    def set_playlist_tester(
        self,
        tester: Callable[..., PlaylistReference],
    ) -> None:
        self._playlist_tester = tester

    def _validated_playlist(self, playlist: PlaylistReference) -> PlaylistReference | None:
        if self._playlist_validator is None:
            return playlist
        validated, error = self._playlist_validator(playlist)
        if not validated and error:
            self._set_feedback("error", error)
        return validated

    def _has_duplicate(
        self,
        playlist: PlaylistReference,
        *,
        ignore_item: QListWidgetItem | None = None,
    ) -> bool:
        for index in range(self.playlist_list.count()):
            item = self.playlist_list.item(index)
            if item is ignore_item:
                continue
            data = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(data, PlaylistReference):
                continue
            if data.identity_key() == playlist.identity_key():
                self._show_warning("That playlist is already in the library.")
                return True
        return False

    def _test_selected_playlist(self) -> None:
        if self._playlist_tester is None:
            self._set_feedback("warning", "Playlist testing is unavailable.")
            return
        current_item = self.playlist_list.currentItem()
        if not current_item:
            return
        playlist = current_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(playlist, PlaylistReference):
            return

        self._tester_task_id += 1
        task_id = self._tester_task_id
        self._tester_identity = playlist.source_identity
        self._tester_worker = create_background_task(task_id, self._playlist_tester, playlist)
        self._tester_worker.signals.progress.connect(self._on_test_progress)
        self._tester_worker.signals.succeeded.connect(self._on_test_succeeded)
        self._tester_worker.signals.failed.connect(self._on_test_failed)
        self._tester_worker.signals.finished.connect(self._on_test_finished)
        self.test_button.setEnabled(False)
        self._set_feedback("warning", "Testing playlist source...")
        self._thread_pool.start(self._tester_worker)

    def _on_test_progress(self, task_id: int, message: str) -> None:
        if self._tester_worker is None or task_id != self._tester_task_id:
            return
        self._set_feedback("warning", message)

    def _on_test_succeeded(self, task_id: int, result: object) -> None:
        if self._tester_worker is None or task_id != self._tester_task_id:
            return
        if not isinstance(result, PlaylistReference):
            return

        identity = self._tester_identity
        # Look the row up by identity: the selection may have moved or the row been removed.
        tested_item = self._find_item_by_identity(identity)
        if tested_item is not None and identity is not None:
            # Merge only probe-owned fields so a concurrent edit that kept the identity survives.
            current = tested_item.data(Qt.ItemDataRole.UserRole)
            merged = replace(
                current,
                channel_count=result.channel_count,
                last_status=result.last_status,
                last_error=result.last_error,
            )
            tested_item.setData(Qt.ItemDataRole.UserRole, merged)
            tested_item.setText(self._item_title(merged))
            self._validation_messages[identity] = (
                result.last_status or "ready",
                result.last_error or f"Verified successfully ({result.channel_count} channels detected).",
            )
        if result.last_status == "warning" and result.last_error:
            self._set_feedback(
                "warning",
                f"Playlist verified with warnings. {result.channel_count} channels detected.",
            )
        else:
            self._set_feedback(
                "ready",
                f"Playlist verified successfully. {result.channel_count} channels detected.",
            )
        if tested_item is not None and tested_item is self.playlist_list.currentItem():
            self._set_details(tested_item.data(Qt.ItemDataRole.UserRole))

    def _on_test_failed(self, task_id: int, message: str) -> None:
        if self._tester_worker is None or task_id != self._tester_task_id:
            return
        tested_item = self._find_item_by_identity(self._tester_identity)
        if tested_item is not None and self._tester_identity is not None:
            self._validation_messages[self._tester_identity] = ("error", message)
            playlist = tested_item.data(Qt.ItemDataRole.UserRole)
            if tested_item is self.playlist_list.currentItem() and isinstance(playlist, PlaylistReference):
                self._set_details(playlist)
        self._set_feedback("error", message)

    def _find_item_by_identity(self, identity: str | None) -> QListWidgetItem | None:
        if identity is None:
            return None
        for index in range(self.playlist_list.count()):
            item = self.playlist_list.item(index)
            if item is None:
                continue
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, PlaylistReference) and data.source_identity == identity:
                return item
        return None

    def _on_test_finished(self, task_id: int) -> None:
        if task_id != self._tester_task_id:
            return
        self._tester_worker = None
        self.test_button.setEnabled(bool(self.playlist_list.selectedItems()))

    def _show_warning(self, message: str) -> None:
        self._set_feedback("error", message)
        QMessageBox.warning(self, "Playlist Manager", message)

    def _item_title(self, playlist: PlaylistReference) -> str:
        source_kind = playlist.source_type.value.upper()
        suffix = "  ·  ACTIVE" if playlist.source_identity == self._active_playlist_path else ""
        return f"{playlist.name}  ·  {source_kind}{suffix}"

    def _set_feedback(self, tone: str, message: str) -> None:
        self.feedback_label.setText(message)
        self.feedback_label.setProperty("stateTone", tone)
        self.feedback_label.style().unpolish(self.feedback_label)
        self.feedback_label.style().polish(self.feedback_label)

    def _set_details(self, playlist: PlaylistReference | None) -> None:
        self.details_placeholder.setVisible(playlist is None)
        self.details_form_host.setVisible(playlist is not None)
        if not playlist:
            for value in (
                self.detail_name,
                self.detail_source,
                self.detail_path,
                self.detail_channels,
                self.detail_loaded,
                self.detail_status,
                self.detail_validation,
            ):
                value.setText("")
            return

        self.detail_name.setText(playlist.name)
        source_map = {
            PlaylistSourceType.FILE: "Local file",
            PlaylistSourceType.URL: "Remote URL",
            PlaylistSourceType.XTREAM: "Xtream Codes",
        }
        self.detail_source.setText(source_map.get(playlist.source_type, "Unknown"))
        self.detail_path.setText(playlist.source_summary())
        self.detail_channels.setText(str(playlist.channel_count) if playlist.channel_count else "Unknown")
        self.detail_loaded.setText(playlist.last_loaded_at or "Never loaded")
        status = playlist.last_status or "Not validated yet"
        if playlist.source_identity == self._active_playlist_path:
            status = f"{status} / Active"
        self.detail_status.setText(status)

        _validation_status, validation_message = self._validation_messages.get(
            playlist.source_identity,
            ("pending", "Use Test Source to verify reachability and parsing."),
        )
        self.detail_validation.setText(validation_message)
