from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtCore import Qt, QTimer
from models.playlist import Playlist, Channel
from models.epg import EPGGuide
from utils.m3u_parser import M3UParser
from utils.epg_parser import EPGParser
from utils.database import Database
from views.main_window import MainWindow
from datetime import datetime
import requests
import tempfile
import os

class PlayerController:
    def __init__(self, main_window: MainWindow):
        self.window = main_window
        self.playlist = Playlist()
        self.db = Database()
        self.current_channel = None
        self.epg_guide = None
        
        # Create timer for EPG updates
        self.epg_timer = QTimer()
        self.epg_timer.setInterval(60000)  # Update every minute
        self.epg_timer.timeout.connect(self._update_epg_display)
        
        # Load saved settings
        self._load_settings()
        
        # Load favorites
        self._load_favorites()
        
        # Connect signals
        self._connect_signals()
        
        # Connect EPG signals
        self.window.load_epg_file_action.triggered.connect(self.load_epg_file)
        self.window.load_epg_url_button.clicked.connect(self.load_epg_url)
        
        # Load last used EPG URL
        last_url = self.db.get_setting('epg_url', '')
        if last_url:
            self.window.epg_url_input.setText(last_url)
    
    def _connect_signals(self):
        # Playlist and channels
        self.window.load_button.clicked.connect(self.load_playlist)
        self.window.load_epg_button.clicked.connect(self.load_epg)
        self.window.category_combo.currentTextChanged.connect(self.category_changed)
        self.window.channel_list.itemClicked.connect(self.channel_selected)
        self.window.favorites_list.itemClicked.connect(self.favorite_selected)
        
        # Playback controls
        self.window.play_button.clicked.connect(self.toggle_playback)
        self.window.stop_button.clicked.connect(self.stop_playback)
        self.window.volume_slider.valueChanged.connect(self.volume_changed)
        
        # Favorites
        self.window.favorite_button.clicked.connect(self.toggle_favorite)
    
    def _load_settings(self):
        # Load and apply volume
        volume = int(self.db.get_setting('volume', '100'))
        self.window.volume_slider.setValue(volume)
        self.window.player_widget.set_volume(volume)
        
        # Load last category
        last_category = self.db.get_setting('last_category', '')
        if last_category:
            index = self.window.category_combo.findText(last_category)
            if index >= 0:
                self.window.category_combo.setCurrentIndex(index)
    
    def _load_favorites(self):
        self.window.favorites_list.clear()
        for channel in self.db.get_favorites():
            self.window.favorites_list.addItem(channel.name)
    
    def load_playlist(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Open M3U Playlist",
            "",
            "M3U Files (*.m3u *.m3u8)"
        )
        
        if file_path:
            try:
                self.playlist = M3UParser.parse(file_path)
                self._update_categories()
                self._update_channel_list()
            except Exception as e:
                QMessageBox.critical(self.window, "Error", f"Failed to load playlist: {str(e)}")
    
    def _update_categories(self):
        self.window.category_combo.clear()
        self.window.category_combo.addItems(self.playlist.categories)
        
        # Select last used category if available
        last_category = self.db.get_setting('last_category', '')
        if last_category in self.playlist.categories:
            self.window.category_combo.setCurrentText(last_category)
    
    def _update_channel_list(self):
        category = self.window.category_combo.currentText()
        self.window.channel_list.clear()
        
        if category:
            channels = self.playlist.get_channels_by_category(category)
            for channel in channels:
                self.window.channel_list.addItem(channel.name)
    
    def category_changed(self, category: str):
        self._update_channel_list()
        self.db.save_setting('last_category', category)
    
    def channel_selected(self, item):
        category = self.window.category_combo.currentText()
        channels = self.playlist.get_channels_by_category(category)
        self.current_channel = channels[self.window.channel_list.row(item)]
        self._play_channel(self.current_channel)
        
        # Update favorite button state
        self.window.favorite_button.setChecked(
            self.db.is_favorite(self.current_channel.url)
        )
    
    def favorite_selected(self, item):
        favorites = self.db.get_favorites()
        self.current_channel = favorites[self.window.favorites_list.row(item)]
        self._play_channel(self.current_channel)
        self.window.favorite_button.setChecked(True)
    
    def _play_channel(self, channel: Channel):
        self.window.player_widget.play(channel.url)
        self.current_channel = channel
        self._update_epg_display()
    
    def toggle_playback(self):
        self.window.player_widget.pause()
    
    def stop_playback(self):
        self.window.player_widget.stop()
    
    def volume_changed(self, value: int):
        self.window.player_widget.set_volume(value)
        self.db.save_setting('volume', str(value))
    
    def toggle_favorite(self, checked: bool):
        if not self.current_channel:
            return
            
        if checked:
            if self.db.add_favorite(self.current_channel):
                self._load_favorites()
            else:
                self.window.favorite_button.setChecked(False)
                QMessageBox.warning(self.window, "Error", "Failed to add favorite")
        else:
            if self.db.remove_favorite(self.current_channel.url):
                self._load_favorites()
            else:
                self.window.favorite_button.setChecked(True)
                QMessageBox.warning(self.window, "Error", "Failed to remove favorite")
    
    def load_epg(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Open EPG File",
            "",
            "XMLTV Files (*.xml);;All Files (*.*)"
        )
        
        if file_path:
            try:
                self.epg_guide = EPGParser.parse_xmltv(file_path)
                self._update_epg_display()
                self.epg_timer.start()
                QMessageBox.information(self.window, "Success", "EPG data loaded successfully")
            except Exception as e:
                QMessageBox.critical(self.window, "Error", f"Failed to load EPG: {str(e)}")
    
    def _update_epg_display(self):
        if not self.current_channel or not self.epg_guide:
            return
            
        # Get EPG data for current channel
        epg_data = self.epg_guide.get_channel_data(self.current_channel.epg_id)
        if not epg_data:
            return
            
        # Get current program
        current_program = epg_data.get_current_program()
        if current_program:
            time_str = (f"{current_program.start_time.strftime('%H:%M')} - "
                       f"{current_program.end_time.strftime('%H:%M')}")
            
            self.window.epg_widget.update_current_program(
                current_program.title,
                time_str,
                current_program.description
            )
            
            # Get upcoming programs
            upcoming = [p for p in epg_data.programs 
                       if p.start_time > datetime.now()][:5]
            self.window.epg_widget.set_upcoming_programs(upcoming) 
    
    def load_epg_file(self):
        """Load EPG from local file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Open EPG File",
            "",
            "XMLTV Files (*.xml);;All Files (*.*)"
        )
        
        if file_path:
            self._load_epg_from_file(file_path)
    
    def load_epg_url(self):
        """Load EPG from URL"""
        url = self.window.epg_url_input.text().strip()
        if not url:
            QMessageBox.warning(self.window, "Error", "Please enter an EPG URL")
            return
            
        try:
            # Download the file
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as tmp_file:
                tmp_file.write(response.content)
                tmp_path = tmp_file.name
            
            # Load the EPG
            success = self._load_epg_from_file(tmp_path)
            
            # Clean up temp file
            os.unlink(tmp_path)
            
            if success:
                # Save URL for next time
                self.db.save_setting('epg_url', url)
                
        except requests.RequestException as e:
            QMessageBox.critical(self.window, "Error", f"Failed to download EPG: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self.window, "Error", f"Failed to load EPG: {str(e)}")
    
    def _load_epg_from_file(self, file_path: str) -> bool:
        """Common EPG loading logic"""
        try:
            self.epg_guide = EPGParser.parse_xmltv(file_path)
            self._update_epg_display()
            self.epg_timer.start()
            QMessageBox.information(self.window, "Success", "EPG data loaded successfully")
            return True
        except Exception as e:
            QMessageBox.critical(self.window, "Error", f"Failed to parse EPG: {str(e)}")
            return False 