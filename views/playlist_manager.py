"""
This module contains the PlaylistManagerDialog class, 
which is responsible for managing the playlist manager dialog.
"""

import tempfile
import os
import requests
import logging
from typing import Optional

# pylint: disable=no-name-in-module
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
    QLineEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal

from controllers.playlist_controller import PlaylistController

logger = logging.getLogger(__name__)


class PlaylistManagerDialog(QDialog):
    """
    This class is responsible for managing the playlist manager dialog.
    """

    playlist_selected = pyqtSignal(str, bool)  # Emits (path, is_url)

    def __init__(self, parent=None, playlist_controller: Optional[PlaylistController] = None):
        """Initialize the playlist manager dialog.
        
        Args:
            parent: The parent widget
            playlist_controller: The playlist controller instance
        """
        super().__init__(parent)
        self.setWindowTitle("Playlist Manager")
        self.setMinimumSize(400, 300)
        
        self.playlist_controller = playlist_controller

        # Create layout
        layout = QVBoxLayout(self)

        # Add header
        header = QLabel("Your Playlists")
        header.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header)

        # Add playlist list
        self.playlist_list = QListWidget()
        layout.addWidget(self.playlist_list)

        # Add buttons
        button_layout = QHBoxLayout()
        
        # Add playlist button
        self.add_button = QPushButton("Add Playlist")
        self.add_button.clicked.connect(self._show_add_menu)
        button_layout.addWidget(self.add_button)
        
        # Remove playlist button
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self.remove_playlist)
        self.remove_button.setEnabled(False)
        button_layout.addWidget(self.remove_button)
        
        # Edit playlist button
        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self.edit_playlist)
        self.edit_button.setEnabled(False)
        button_layout.addWidget(self.edit_button)
        
        layout.addLayout(button_layout)

        # Connect signals
        self.playlist_list.itemSelectionChanged.connect(self.selection_changed)
        self.playlist_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.playlist_list.customContextMenuRequested.connect(self._show_context_menu)

        # Load saved playlists if we have a controller
        if self.playlist_controller:
            self._load_saved_playlists()

    def _load_saved_playlists(self):
        """Load saved playlists from the controller."""
        try:
            if hasattr(self.playlist_controller, 'get_saved_playlists'):
                playlists = self.playlist_controller.get_saved_playlists()
                for playlist in playlists:
                    self._add_playlist_entry(playlist['path'], playlist.get('is_url', False))
        except Exception as e:
            logger.error(f"Failed to load saved playlists: {str(e)}")

    def _show_add_menu(self):
        """Show the add playlist menu."""
        menu = QMenu(self)
        file_action = menu.addAction("Add from File")
        url_action = menu.addAction("Add from URL")
        xtream_action = menu.addAction("Add XTREAM Service")
        
        action = menu.exec(self.add_button.mapToGlobal(self.add_button.rect().bottomLeft()))
        
        if action == file_action:
            self.add_playlist_file()
        elif action == url_action:
            self.add_playlist_url()
        elif action == xtream_action:
            self.add_xtream_service()

    def selection_changed(self):
        """Handle playlist selection change."""
        has_selection = bool(self.playlist_list.selectedItems())
        self.remove_button.setEnabled(has_selection)
        self.edit_button.setEnabled(has_selection)

    def add_playlist_file(self):
        """Add a playlist from a file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Playlist File",
            "",
            "Playlist Files (*.m3u *.m3u8);;All Files (*.*)"
        )
        
        if file_path:
            self._add_playlist_entry(file_path)
            if self.playlist_controller:
                self.playlist_controller.save_playlist(file_path, False)

    def add_playlist_url(self):
        """Add a playlist from a URL."""
        url, ok = QInputDialog.getText(
            self,
            "Add Playlist URL",
            "Enter playlist URL:"
        )
        
        if ok and url:
            self._add_playlist_entry(url, True)
            if self.playlist_controller:
                self.playlist_controller.save_playlist(url, True)

    def add_xtream_service(self):
        """Add an XTREAM service."""
        # Get URL
        url, ok = QInputDialog.getText(
            self,
            "Add XTREAM Service",
            "Enter XTREAM service URL:",
            text="http://example.com/player_api.php"
        )
        
        if not ok or not url:
            return
            
        # Get username
        username, ok = QInputDialog.getText(
            self,
            "Add XTREAM Service",
            "Enter username:"
        )
        
        if not ok or not username:
            return
            
        # Get password
        password, ok = QInputDialog.getText(
            self,
            "Add XTREAM Service",
            "Enter password:",
            echo=QLineEdit.EchoMode.Password
        )
        
        if ok and url and username and password:
            # Save credentials
            if self.playlist_controller and hasattr(self.playlist_controller, 'settings'):
                self.playlist_controller.settings.save_setting("xtream_username", username)
                self.playlist_controller.settings.save_setting("xtream_password", password)
            
            # Add playlist entry
            self._add_playlist_entry(url, True)
            
            # Save playlist if controller is available
            if self.playlist_controller and hasattr(self.playlist_controller, 'save_playlist'):
                self.playlist_controller.save_playlist(url, True)

    def _add_playlist_entry(self, path: str, is_url: bool = False):
        """Add a playlist entry to the list.
        
        Args:
            path: The path or URL of the playlist
            is_url: Whether the path is a URL
        """
        item = QListWidgetItem(path)
        item.setData(Qt.ItemDataRole.UserRole, is_url)
        self.playlist_list.addItem(item)

    def remove_playlist(self):
        """Remove the selected playlist."""
        selected_items = self.playlist_list.selectedItems()
        if not selected_items:
            return
            
        item = selected_items[0]
        path = item.text()
        is_url = item.data(Qt.ItemDataRole.UserRole)
        
        if self.playlist_controller:
            self.playlist_controller.remove_playlist(path, is_url)
        
        self.playlist_list.takeItem(self.playlist_list.row(item))

    def select_playlist(self):
        """Select the current playlist."""
        selected_items = self.playlist_list.selectedItems()
        if not selected_items:
            return
            
        item = selected_items[0]
        path = item.text()
        is_url = item.data(Qt.ItemDataRole.UserRole)
        
        self.playlist_selected.emit(path, is_url)
        self.accept()

    def get_playlists(self):
        """Get all playlists."""
        playlists = []
        for i in range(self.playlist_list.count()):
            item = self.playlist_list.item(i)
            playlists.append({
                'path': item.text(),
                'is_url': item.data(Qt.ItemDataRole.UserRole)
            })
        return playlists

    def set_playlists(self, playlists):
        """Set the playlists.
        
        Args:
            playlists: List of dictionaries containing path and is_url
        """
        self.playlist_list.clear()
        for playlist in playlists:
            self._add_playlist_entry(playlist['path'], playlist.get('is_url', False))

    def _show_context_menu(self, position):
        """Show the context menu.
        
        Args:
            position: The position where the menu should be shown
        """
        menu = QMenu()
        select_action = menu.addAction("Select")
        edit_action = menu.addAction("Edit")
        remove_action = menu.addAction("Remove")
        
        action = menu.exec(self.playlist_list.mapToGlobal(position))
        
        if action == select_action:
            self.select_playlist()
        elif action == edit_action:
            self.edit_playlist()
        elif action == remove_action:
            self.remove_playlist()

    def edit_playlist(self):
        """Edit the selected playlist."""
        selected_items = self.playlist_list.selectedItems()
        if not selected_items:
            return
            
        item = selected_items[0]
        path = item.text()
        is_url = item.data(Qt.ItemDataRole.UserRole)
        
        if is_url:
            new_url, ok = QInputDialog.getText(
                self,
                "Edit Playlist URL",
                "Enter new URL:",
                text=path
            )
            if ok and new_url:
                item.setText(new_url)
                if self.playlist_controller:
                    self.playlist_controller.update_playlist(path, new_url, True)
        else:
            new_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select New Playlist File",
                os.path.dirname(path),
                "Playlist Files (*.m3u *.m3u8);;All Files (*.*)"
            )
            if new_path:
                item.setText(new_path)
                if self.playlist_controller:
                    self.playlist_controller.update_playlist(path, new_path, False)

    def close_event(self, event):
        """Handle dialog close event."""
        if self.playlist_controller:
            playlists = self.get_playlists()
            self.playlist_controller.save_playlists(playlists)
        super().closeEvent(event)
