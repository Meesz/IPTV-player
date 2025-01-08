from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QListWidget, QListWidgetItem, QLabel, QInputDialog, 
                            QMessageBox, QFileDialog, QMenu)
from PyQt6.QtCore import Qt, pyqtSignal
import requests
import tempfile
import os

class PlaylistManagerDialog(QDialog):
    playlist_selected = pyqtSignal(str, bool)  # Emits (path, is_url)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Playlist Manager")
        self.setMinimumSize(400, 300)
        
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
        
        # Create Add button with dropdown menu
        self.add_button = QPushButton("Add Playlist")
        self.add_menu = QMenu(self)
        self.add_menu.addAction("From File...", self.add_playlist_file)
        self.add_menu.addAction("From URL...", self.add_playlist_url)
        self.add_button.setMenu(self.add_menu)
        
        self.remove_button = QPushButton("Remove")
        self.select_button = QPushButton("Select")
        self.cancel_button = QPushButton("Cancel")
        
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addWidget(self.select_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        # Connect signals
        self.remove_button.clicked.connect(self.remove_playlist)
        self.select_button.clicked.connect(self.select_playlist)
        self.cancel_button.clicked.connect(self.reject)
        self.playlist_list.itemDoubleClicked.connect(self.select_playlist)
        
        # Disable buttons initially
        self.remove_button.setEnabled(False)
        self.select_button.setEnabled(False)
        
        # Connect selection changed
        self.playlist_list.itemSelectionChanged.connect(self.selection_changed)
    
    def selection_changed(self):
        has_selection = bool(self.playlist_list.selectedItems())
        self.remove_button.setEnabled(has_selection)
        self.select_button.setEnabled(has_selection)
    
    def add_playlist_file(self):
        """Add playlist from local file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open M3U Playlist",
            "",
            "M3U Files (*.m3u *.m3u8)"
        )
        
        if file_path:
            self._add_playlist_entry(file_path)
    
    def add_playlist_url(self):
        """Add playlist from URL"""
        url, ok = QInputDialog.getText(
            self,
            "Add Playlist URL",
            "Enter the M3U playlist URL:",
            text="http://"
        )
        
        if ok and url:
            try:
                # Download the playlist
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                # Save to temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.m3u8') as tmp_file:
                    tmp_file.write(response.content)
                    tmp_path = tmp_file.name
                
                # Add to playlist list with URL as source
                self._add_playlist_entry(url, is_url=True)
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to download playlist: {str(e)}"
                )
    
    def _add_playlist_entry(self, path: str, is_url: bool = False):
        """Common method to add playlist entry"""
        name, ok = QInputDialog.getText(
            self,
            "Playlist Name",
            "Enter a name for this playlist:",
            text=os.path.basename(path) if not is_url else "URL Playlist"
        )
        
        if ok and name:
            item = QListWidgetItem(name)
            # Store both path and type
            item.setData(Qt.ItemDataRole.UserRole, {
                'path': path,
                'is_url': is_url
            })
            self.playlist_list.addItem(item)
    
    def remove_playlist(self):
        current_item = self.playlist_list.currentItem()
        if current_item:
            confirm = QMessageBox.question(
                self,
                "Confirm Removal",
                f"Are you sure you want to remove '{current_item.text()}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if confirm == QMessageBox.StandardButton.Yes:
                self.playlist_list.takeItem(self.playlist_list.row(current_item))
    
    def select_playlist(self):
        current_item = self.playlist_list.currentItem()
        if current_item:
            data = current_item.data(Qt.ItemDataRole.UserRole)
            self.playlist_selected.emit(data['path'], data['is_url'])
            self.accept()
    
    def get_playlists(self):
        """Get all playlists as list of (name, path, is_url) tuples"""
        playlists = []
        for i in range(self.playlist_list.count()):
            item = self.playlist_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            playlists.append((
                item.text(),
                data['path'],
                data['is_url']
            ))
        return playlists
    
    def set_playlists(self, playlists):
        """Set playlists from list of (name, path, is_url) tuples"""
        self.playlist_list.clear()
        for name, path, is_url in playlists:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, {
                'path': path,
                'is_url': is_url
            })
            self.playlist_list.addItem(item) 