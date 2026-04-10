import os
from typing import Callable, Sequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.models import PlaylistReference


class PlaylistManagerDialog(QDialog):
    """Dialog for adding, editing, and selecting playlist references."""

    playlist_selected = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("playlist_dialog")
        self.setWindowTitle("Playlist Manager")
        self.setMinimumSize(760, 420)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint)
        self._active_playlist_path = ""
        self._playlist_validator: Callable[[PlaylistReference], PlaylistReference | None] | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(14)

        title = QLabel("Playlist Library")
        title.setObjectName("dialog_title")
        root_layout.addWidget(title)

        shell = QFrame()
        shell.setObjectName("playlist_dialog_card")
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(16, 16, 16, 16)
        shell_layout.setSpacing(14)

        list_layout = QVBoxLayout()
        list_layout.setSpacing(10)

        self.header = QLabel("Saved playlists")
        self.header.setObjectName("panel_heading")
        list_layout.addWidget(self.header)

        self.playlist_list = QListWidget()
        self.playlist_list.itemSelectionChanged.connect(self._selection_changed)
        self.playlist_list.itemDoubleClicked.connect(self._edit_playlist)
        self.playlist_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.playlist_list.customContextMenuRequested.connect(self._show_context_menu)
        list_layout.addWidget(self.playlist_list, stretch=1)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)

        self.add_button = QPushButton("Add Playlist")
        self.add_button.setProperty("accent", True)
        self.add_menu = QMenu(self)
        self.add_menu.addAction("From File...", self._add_playlist_file)
        self.add_menu.addAction("From URL...", self._add_playlist_url)
        self.add_button.setMenu(self.add_menu)

        self.edit_button = QPushButton("Edit")
        self.edit_button.setEnabled(False)
        self.remove_button = QPushButton("Remove")
        self.remove_button.setEnabled(False)
        self.select_button = QPushButton("Select")
        self.select_button.setEnabled(False)

        self.edit_button.clicked.connect(self._edit_playlist)
        self.remove_button.clicked.connect(self._remove_playlist)
        self.select_button.clicked.connect(self._select_playlist)

        button_row.addWidget(self.add_button)
        button_row.addWidget(self.edit_button)
        button_row.addWidget(self.remove_button)
        button_row.addStretch()
        button_row.addWidget(self.select_button)

        list_layout.addLayout(button_row)
        shell_layout.addLayout(list_layout, stretch=3)

        self.details_card = QFrame()
        self.details_card.setObjectName("playlist_detail_card")
        details_layout = QVBoxLayout(self.details_card)
        details_layout.setContentsMargins(16, 16, 16, 16)
        details_layout.setSpacing(10)

        details_heading = QLabel("Details")
        details_heading.setObjectName("panel_heading")
        details_layout.addWidget(details_heading)

        self.detail_name = self._detail_label("Name")
        self.detail_source = self._detail_label("Source")
        self.detail_path = self._detail_label("Path")
        self.detail_channels = self._detail_label("Channels")
        self.detail_loaded = self._detail_label("Last loaded")
        self.detail_status = self._detail_label("Status")

        for label in (
            self.detail_name,
            self.detail_source,
            self.detail_path,
            self.detail_channels,
            self.detail_loaded,
            self.detail_status,
        ):
            details_layout.addWidget(label)
        details_layout.addStretch()

        shell_layout.addWidget(self.details_card, stretch=2)
        root_layout.addWidget(shell, stretch=1)

        footer = QHBoxLayout()
        footer.addStretch()
        self.cancel_button = QPushButton("Close")
        self.cancel_button.setProperty("ghost", True)
        self.cancel_button.clicked.connect(self.reject)
        footer.addWidget(self.cancel_button)
        root_layout.addLayout(footer)

        self._set_details(None)

    @staticmethod
    def _detail_label(title: str) -> QLabel:
        label = QLabel(f"{title}: -")
        label.setObjectName("playlist_detail_label")
        label.setWordWrap(True)
        return label

    def _selection_changed(self) -> None:
        has_selection = bool(self.playlist_list.selectedItems())
        self.remove_button.setEnabled(has_selection)
        self.select_button.setEnabled(has_selection)
        self.edit_button.setEnabled(has_selection)

        item = self.playlist_list.currentItem()
        data = item.data(Qt.ItemDataRole.UserRole) if item else None
        self._set_details(data if isinstance(data, PlaylistReference) else None)

    def _add_playlist_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open M3U Playlist", "", "M3U Files (*.m3u *.m3u8)"
        )
        if file_path:
            self._add_playlist_entry(file_path, is_url=False)

    def _add_playlist_url(self) -> None:
        url, ok = QInputDialog.getText(
            self, "Add Playlist URL", "Enter the M3U playlist URL:"
        )
        if ok and url:
            self._add_playlist_entry(url.strip(), is_url=True)

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
            PlaylistReference(name=name, path=path, is_url=is_url)
        )
        if not playlist or self._has_duplicate(playlist):
            return
        self._add_playlist_item(playlist)

    def _add_playlist_item(self, playlist: PlaylistReference) -> None:
        item = QListWidgetItem(self._item_title(playlist))
        item.setData(Qt.ItemDataRole.UserRole, playlist)
        self.playlist_list.addItem(item)

    def _remove_playlist(self) -> None:
        current_item = self.playlist_list.currentItem()
        if not current_item:
            return
        playlist = current_item.data(Qt.ItemDataRole.UserRole)
        if isinstance(playlist, PlaylistReference) and playlist.path == self._active_playlist_path:
            self._show_warning("The active playlist cannot be removed.")
            return
        confirm = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Remove '{current_item.text()}' from the library?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.playlist_list.takeItem(self.playlist_list.row(current_item))
            self._set_details(None)

    def _select_playlist(self) -> None:
        current_item = self.playlist_list.currentItem()
        if not current_item:
            return
        playlist = current_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(playlist, PlaylistReference):
            return
        self.playlist_selected.emit(playlist.path, playlist.is_url)
        self.accept()

    def _edit_playlist(self) -> None:
        current_item = self.playlist_list.currentItem()
        if not current_item:
            return

        data = current_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, PlaylistReference):
            return
        name, ok = QInputDialog.getText(
            self, "Edit Playlist Name", "Enter new name:", text=data.name
        )
        if not ok or not name:
            return

        path = data.path
        is_url = data.is_url
        if is_url:
            new_path, ok = QInputDialog.getText(
                self,
                "Edit Playlist URL",
                "Enter new URL:",
                text=path,
            )
            if not ok or not new_path:
                return
            if data.path == self._active_playlist_path and new_path.strip() != data.path:
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
                if data.path == self._active_playlist_path and new_path != data.path:
                    self._show_warning("The active playlist source cannot be changed while it is active.")
                    return
                path = new_path

        playlist = self._validated_playlist(
            PlaylistReference(
                name=name.strip(),
                path=path,
                is_url=is_url,
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
        self._set_details(playlist)

    def _show_context_menu(self, position) -> None:
        item = self.playlist_list.itemAt(position)
        if not item:
            return
        menu = QMenu()
        edit_action = menu.addAction("Edit")
        remove_action = menu.addAction("Remove")
        action = menu.exec(self.playlist_list.mapToGlobal(position))
        if action == edit_action:
            self._edit_playlist()
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
                    is_url=data.is_url,
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
        validator: Callable[[PlaylistReference], PlaylistReference | None],
    ) -> None:
        self._playlist_validator = validator

    def _validated_playlist(self, playlist: PlaylistReference) -> PlaylistReference | None:
        if self._playlist_validator is None:
            return playlist
        return self._playlist_validator(playlist)

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
            if (data.path, data.is_url) == (playlist.path, playlist.is_url):
                self._show_warning("That playlist is already in the library.")
                return True
        return False

    def _show_warning(self, message: str) -> None:
        QMessageBox.warning(self, "Playlist Manager", message)

    def _item_title(self, playlist: PlaylistReference) -> str:
        source_kind = "URL" if playlist.is_url else "FILE"
        suffix = " [ACTIVE]" if playlist.path == self._active_playlist_path else ""
        return f"{playlist.name} [{source_kind}]{suffix}"

    def _set_details(self, playlist: PlaylistReference | None) -> None:
        if not playlist:
            self.detail_name.setText("Name: -")
            self.detail_source.setText("Source: -")
            self.detail_path.setText("Path: -")
            self.detail_channels.setText("Channels: -")
            self.detail_loaded.setText("Last loaded: -")
            self.detail_status.setText("Status: -")
            return

        self.detail_name.setText(f"Name: {playlist.name}")
        self.detail_source.setText(f"Source: {'Remote URL' if playlist.is_url else 'Local file'}")
        self.detail_path.setText(f"Path: {playlist.path}")
        self.detail_channels.setText(
            f"Channels: {playlist.channel_count if playlist.channel_count else 'Unknown'}"
        )
        self.detail_loaded.setText(
            f"Last loaded: {playlist.last_loaded_at or 'Never loaded'}"
        )
        status = playlist.last_status or "Not validated yet"
        if playlist.path == self._active_playlist_path:
            status = f"{status} / Active"
        self.detail_status.setText(f"Status: {status}")
