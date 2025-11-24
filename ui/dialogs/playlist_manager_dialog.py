import os
import requests
import tempfile
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QInputDialog,
    QMessageBox,
    QFileDialog,
    QMenu,
)
from PyQt6.QtCore import Qt, pyqtSignal

class PlaylistManagerDialog(QDialog):
    """Dialog for managing playlists."""

    playlist_selected = pyqtSignal(str, bool)  # Emits (path, is_url)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Playlist Manager")
        self.setMinimumSize(400, 300)
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

        button_layout = QHBoxLayout()

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

        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addWidget(self.select_button)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

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
            self._add_playlist_entry(file_path)

    def _add_playlist_url(self):
        url, ok = QInputDialog.getText(
            self, "Add Playlist URL", "Enter the M3U playlist URL:", text="http://"
        )
        if ok and url:
            try:
                # Verify URL validity by a quick HEAD request or similar if desired
                # For now just add it
                self._add_playlist_entry(url, is_url=True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add playlist: {str(e)}")

    def _add_playlist_entry(self, path: str, is_url: bool = False):
        name, ok = QInputDialog.getText(
            self,
            "Playlist Name",
            "Enter a name for this playlist:",
            text=os.path.basename(path) if not is_url else "URL Playlist",
        )

        if ok and name:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, {"path": path, "is_url": is_url})
            item.setToolTip(f"{'URL' if is_url else 'File'}: {path}")
            self.playlist_list.addItem(item)

    def _remove_playlist(self):
        current_item = self.playlist_list.currentItem()
        if current_item:
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
            data = current_item.data(Qt.ItemDataRole.UserRole)
            self.playlist_selected.emit(data["path"], data["is_url"])
            self.accept()

    def _edit_playlist(self):
        current_item = self.playlist_list.currentItem()
        if not current_item:
            return

        data = current_item.data(Qt.ItemDataRole.UserRole)
        is_url = data["is_url"]

        name, ok = QInputDialog.getText(
            self, "Edit Playlist Name", "Enter new name:", text=current_item.text()
        )
        if not ok:
            return

        if is_url:
            path, ok = QInputDialog.getText(
                self, "Edit Playlist URL", "Enter new URL:", text=data["path"]
            )
        else:
            path, ok = QFileDialog.getOpenFileName(
                self, "Select New Playlist File", data["path"], "M3U Files (*.m3u *.m3u8)"
            )

        if ok and path:
            current_item.setText(name)
            current_item.setData(Qt.ItemDataRole.UserRole, {"path": path, "is_url": is_url})
            current_item.setToolTip(f"{'URL' if is_url else 'File'}: {path}")

    def _show_context_menu(self, position):
        item = self.playlist_list.itemAt(position)
        if item:
            menu = QMenu()
            edit_action = menu.addAction("Edit")
            remove_action = menu.addAction("Remove")
            action = menu.exec(self.playlist_list.mapToGlobal(position))
            
            if action == edit_action:
                self._edit_playlist()
            elif action == remove_action:
                self._remove_playlist()

    def get_playlists(self):
        playlists = []
        for i in range(self.playlist_list.count()):
            item = self.playlist_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            playlists.append((item.text(), data["path"], data["is_url"]))
        return playlists

    def set_playlists(self, playlists):
        self.playlist_list.clear()
        for name, path, is_url in playlists:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, {"path": path, "is_url": is_url})
            item.setToolTip(f"{'URL' if is_url else 'File'}: {path}")
            self.playlist_list.addItem(item)
