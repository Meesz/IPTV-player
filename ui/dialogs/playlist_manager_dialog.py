import os
from typing import Sequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QInputDialog,
    QMenu,
    QVBoxLayout,
    QFileDialog,
    QMessageBox,
)

from core.models import PlaylistReference


class PlaylistManagerDialog(QDialog):
    """Dialog for adding, editing, and selecting playlist references."""

    playlist_selected = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Playlist Manager")
        self.setMinimumSize(460, 320)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel("Your Playlists")
        header.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header)

        self.playlist_list = QListWidget()
        self.playlist_list.itemSelectionChanged.connect(self._selection_changed)
        self.playlist_list.itemDoubleClicked.connect(self._edit_playlist)
        self.playlist_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.playlist_list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.playlist_list)

        buttons = QHBoxLayout()

        self.add_button = QPushButton("Add Playlist")
        self.add_menu = QMenu(self)
        self.add_menu.addAction("From File...", self._add_playlist_file)
        self.add_menu.addAction("From URL...", self._add_playlist_url)
        self.add_button.setMenu(self.add_menu)

        self.edit_button = QPushButton("Edit")
        self.edit_button.setEnabled(False)
        self.edit_button.clicked.connect(self._edit_playlist)

        self.remove_button = QPushButton("Remove")
        self.remove_button.setEnabled(False)
        self.remove_button.clicked.connect(self._remove_playlist)

        self.select_button = QPushButton("Select")
        self.select_button.setEnabled(False)
        self.select_button.clicked.connect(self._select_playlist)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        buttons.addWidget(self.add_button)
        buttons.addWidget(self.edit_button)
        buttons.addWidget(self.remove_button)
        buttons.addWidget(self.select_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)

    def _selection_changed(self):
        has_selection = bool(self.playlist_list.selectedItems())
        self.remove_button.setEnabled(has_selection)
        self.select_button.setEnabled(has_selection)
        self.edit_button.setEnabled(has_selection)

    def _add_playlist_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open M3U Playlist", "", "M3U Files (*.m3u *.m3u8)"
        )
        if file_path:
            self._add_playlist_entry(file_path, is_url=False)

    def _add_playlist_url(self):
        url, ok = QInputDialog.getText(
            self, "Add Playlist URL", "Enter the M3U playlist URL:"
        )
        if ok and url:
            self._add_playlist_entry(url.strip(), is_url=True)

    def _add_playlist_entry(self, path: str, is_url: bool = False):
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
        playlist = PlaylistReference(name=name, path=path, is_url=is_url)
        item = QListWidgetItem(name)
        item.setData(Qt.ItemDataRole.UserRole, playlist)
        item.setToolTip(f"{'URL' if is_url else 'File'}: {path}")
        self.playlist_list.addItem(item)

    def _remove_playlist(self):
        current_item = self.playlist_list.currentItem()
        if not current_item:
            return
        confirm = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Are you sure you want to remove '{current_item.text()}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.playlist_list.takeItem(self.playlist_list.row(current_item))

    def _select_playlist(self):
        current_item = self.playlist_list.currentItem()
        if current_item:
            playlist = current_item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(playlist, PlaylistReference):
                return
            self.playlist_selected.emit(playlist.path, playlist.is_url)
            self.accept()

    def _edit_playlist(self):
        current_item = self.playlist_list.currentItem()
        if not current_item:
            return

        data = current_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, PlaylistReference):
            return
        name, ok = QInputDialog.getText(
            self, "Edit Playlist Name", "Enter new name:", text=current_item.text()
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
            path = new_path.strip()
        else:
            new_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select New Playlist File",
                path,
                "M3U Files (*.m3u *.m3u8)",
            )
            if new_path:
                path = new_path

        current_item.setText(name.strip())
        current_item.setData(
            Qt.ItemDataRole.UserRole,
            PlaylistReference(name=name.strip(), path=path, is_url=is_url),
        )
        current_item.setToolTip(f"{'URL' if is_url else 'File'}: {path}")

    def _show_context_menu(self, position):
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
        for i in range(self.playlist_list.count()):
            item = self.playlist_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(data, PlaylistReference):
                continue
            playlists.append(
                PlaylistReference(
                    name=data.name,
                    path=data.path,
                    is_url=data.is_url,
                )
            )
        return playlists

    def set_playlists(self, playlists: Sequence[PlaylistReference]) -> None:
        self.playlist_list.clear()
        for playlist in playlists:
            self._add_item(playlist.name, playlist.path, playlist.is_url)
