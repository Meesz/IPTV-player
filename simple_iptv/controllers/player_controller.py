from PyQt6.QtWidgets import QFileDialog, QMessageBox, QDialog
from PyQt6.QtCore import Qt, QTimer
from models.playlist import Playlist, Channel
from models.epg import EPGGuide
from utils.m3u_parser import M3UParser
from utils.epg_parser import EPGParser
from utils.database import Database
from utils.themes import Themes
from views.main_window import MainWindow
from views.notification import NotificationType
from datetime import datetime
import requests
import tempfile
import os
from views.playlist_manager import PlaylistManagerDialog
import logging

logger = logging.getLogger(__name__)

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
        
        # Create search timer for debouncing
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)  # 300ms debounce
        self.search_timer.timeout.connect(self._perform_search)
        
        # Connect signals
        self._connect_signals()
        
        # Load saved settings
        self._load_settings()
        
        # Load favorites
        self._load_favorites()
        
        # Load last playlist and EPG
        self._load_last_playlist()
        self._load_last_epg()
    
    def _load_favorites(self):
        """Load favorite channels from database"""
        self.window.favorites_list.clear()
        for channel in self.db.get_favorites():
            self.window.favorites_list.addItem(channel.name)
    
    def _connect_signals(self):
        # Playlist and channels
        self.window.load_button.clicked.connect(self.load_playlist)
        self.window.category_combo.currentTextChanged.connect(self.category_changed)
        self.window.channel_list.itemClicked.connect(self.channel_selected)
        self.window.favorites_list.itemClicked.connect(self.favorite_selected)
        
        # EPG
        self.window.load_epg_file_action.triggered.connect(self.load_epg_file)
        self.window.load_epg_url_button.clicked.connect(self.load_epg_url)
        
        # Playback controls
        self.window.play_button.clicked.connect(self.toggle_playback)
        self.window.stop_button.clicked.connect(self.stop_playback)
        self.window.volume_slider.valueChanged.connect(self.volume_changed)
        
        # Favorites
        self.window.favorite_button.clicked.connect(self.toggle_favorite)
        
        # Theme
        self.window.light_theme_action.triggered.connect(lambda: self.change_theme('light'))
        self.window.dark_theme_action.triggered.connect(lambda: self.change_theme('dark'))
        
        # Search
        self.window.search_bar.textChanged.connect(self._search_changed)
        
        # Connect menu actions
        self.window.playlist_manager_action.triggered.connect(self.show_playlist_manager)
    
    def _load_settings(self):
        # Load volume
        volume = int(self.db.get_setting('volume', '100'))
        self.window.volume_slider.setValue(volume)
        self.window.player_widget.set_volume(volume)
        
        # Load theme
        theme = self.db.get_setting('theme', 'dark')
        self.change_theme(theme, save=False)
        
        # Load last category
        last_category = self.db.get_setting('last_category', '')
        if last_category:
            index = self.window.category_combo.findText(last_category)
            if index >= 0:
                self.window.category_combo.setCurrentIndex(index)
    
    def change_theme(self, theme: str, save: bool = True):
        if theme == 'light':
            self.window.apply_theme(Themes.get_light_theme())
        else:
            self.window.apply_theme(Themes.get_dark_theme())
        
        if save:
            self.db.save_setting('theme', theme)
    
    def _search_changed(self, text: str):
        """Debounce search input"""
        self.search_timer.start()
    
    def _perform_search(self):
        """Actually perform the search"""
        search_text = self.window.search_bar.text().lower()
        
        if not search_text:
            self._update_channel_list()
            return
        
        # Search in current category
        category = self.window.category_combo.currentText()
        channels = self.playlist.get_channels_by_category(category)
        
        # Filter channels
        matched_channels = [
            channel for channel in channels
            if search_text in channel.name.lower()
        ]
        
        # Update list
        self.window.channel_list.clear()
        for channel in matched_channels:
            self.window.channel_list.addItem(channel.name)
    
    def load_playlist(self):
        logger.debug("Opening file dialog for playlist selection")
        file_path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Open M3U Playlist",
            "",
            "M3U Files (*.m3u *.m3u8)"
        )
        
        logger.debug(f"Selected file path: {file_path}")
        
        if file_path:
            try:
                logger.debug("Attempting to parse playlist")
                self.playlist = M3UParser.parse(file_path)
                logger.debug(f"Parsed playlist with {len(self.playlist.channels)} channels")
                
                logger.debug("Updating categories")
                self._update_categories()
                logger.debug("Updating channel list")
                self._update_channel_list()
                
                # Save the playlist path
                logger.debug(f"Saving playlist path to database: {file_path}")
                self.db.save_setting('last_playlist', file_path)
                
                self.window.show_notification(
                    "Playlist loaded successfully",
                    NotificationType.SUCCESS
                )
            except Exception as e:
                logger.error(f"Failed to load playlist: {str(e)}", exc_info=True)
                self.window.show_notification(
                    f"Failed to load playlist: {str(e)}",
                    NotificationType.ERROR
                )
    
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
        try:
            self.window.player_widget.play(channel.url)
            self.current_channel = channel
            self._update_epg_display()
            self.window.show_notification(
                f"Playing: {channel.name}",
                NotificationType.INFO
            )
        except Exception as e:
            error_msg = str(e)
            if "unable to open the MRL" in error_msg.lower():
                self.window.show_notification(
                    f"Channel '{channel.name}' is not available",
                    NotificationType.ERROR
                )
            else:
                self.window.show_notification(
                    f"Failed to play channel: {str(e)}",
                    NotificationType.ERROR
                )
    
    def toggle_playback(self):
        if self.window.player_widget.vlc_available:
            self.window.player_widget.pause()
            status = "Paused" if self.window.player_widget.is_paused() else "Playing"
            self.window.show_notification(status, NotificationType.INFO)
    
    def stop_playback(self):
        if self.window.player_widget.vlc_available:
            self.window.player_widget.stop()
            self.window.show_notification("Playback stopped", NotificationType.INFO)
    
    def volume_changed(self, value: int):
        self.window.player_widget.set_volume(value)
        self.db.save_setting('volume', str(value))
        if value == 0:
            self.window.show_notification("Muted", NotificationType.INFO)
        elif value == 100:
            self.window.show_notification("Maximum volume", NotificationType.INFO)
    
    def toggle_favorite(self, checked: bool):
        if not self.current_channel:
            return
            
        if checked:
            if self.db.add_favorite(self.current_channel):
                self._load_favorites()
                self.window.show_notification(
                    f"Added {self.current_channel.name} to favorites",
                    NotificationType.SUCCESS
                )
            else:
                self.window.favorite_button.setChecked(False)
                self.window.show_notification(
                    "Failed to add favorite",
                    NotificationType.ERROR
                )
        else:
            if self.db.remove_favorite(self.current_channel.url):
                self._load_favorites()
                self.window.show_notification(
                    f"Removed {self.current_channel.name} from favorites",
                    NotificationType.SUCCESS
                )
            else:
                self.window.favorite_button.setChecked(True)
                self.window.show_notification(
                    "Failed to remove favorite",
                    NotificationType.ERROR
                )
    
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
        epg_id = self.current_channel.epg_id
        if not epg_id:
            self.window.epg_widget.update_current_program(
                "No EPG ID available",
                "",
                "This channel does not have EPG information"
            )
            return
            
        epg_data = self.epg_guide.get_channel_data(epg_id)
        if not epg_data:
            self.window.epg_widget.update_current_program(
                "No EPG data available",
                "",
                "No program information found for this channel"
            )
            return
            
        # Get current program
        current_time = datetime.now()
        current_program = epg_data.get_current_program(current_time)
        
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
                       if p.start_time > current_time][:5]
            self.window.epg_widget.set_upcoming_programs(upcoming)
        else:
            self.window.epg_widget.update_current_program(
                "No current program",
                "",
                "No program information available for current time"
            )
    
    def load_epg_file(self):
        """Load EPG from local file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Open EPG File",
            "",
            "XMLTV Files (*.xml);;All Files (*.*)"
        )
        
        if file_path:
            if self._load_epg_from_file(file_path):
                # Save the EPG file path
                self.db.save_setting('last_epg_file', file_path)
    
    def load_epg_url(self):
        url = self.window.epg_url_input.text().strip()
        if not url:
            self.window.show_notification(
                "Please enter an EPG URL",
                NotificationType.WARNING
            )
            return
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as tmp_file:
                tmp_file.write(response.content)
                tmp_path = tmp_file.name
            
            success = self._load_epg_from_file(tmp_path)
            os.unlink(tmp_path)
            
            if success:
                self.db.save_setting('epg_url', url)
                self.window.show_notification(
                    "EPG loaded successfully",
                    NotificationType.SUCCESS
                )
        except requests.RequestException as e:
            self.window.show_notification(
                f"Failed to download EPG: {str(e)}",
                NotificationType.ERROR
            )
        except Exception as e:
            self.window.show_notification(
                f"Failed to load EPG: {str(e)}",
                NotificationType.ERROR
            )
    
    def _load_epg_from_file(self, file_path: str) -> bool:
        try:
            self.epg_guide = EPGParser.parse_xmltv(file_path)
            self._update_epg_display()
            self.epg_timer.start()
            self.window.show_notification(
                "EPG data loaded successfully",
                NotificationType.SUCCESS
            )
            return True
        except Exception as e:
            self.window.show_notification(
                f"Failed to parse EPG: {str(e)}",
                NotificationType.ERROR
            )
            return False 
    
    def _load_last_playlist(self):
        """Load the last used playlist if available"""
        playlist_path = self.db.get_setting('last_playlist')
        is_url = self.db.get_setting('last_playlist_is_url') == 'true'
        
        if playlist_path:
            try:
                logger.debug(f"Loading last playlist from {'URL' if is_url else 'path'}: {playlist_path}")
                self.load_playlist_from_path(playlist_path, is_url)
                self.window.show_notification(
                    "Previous playlist loaded",
                    NotificationType.SUCCESS
                )
            except Exception as e:
                logger.error(f"Failed to load previous playlist: {str(e)}", exc_info=True)
                self.window.show_notification(
                    f"Failed to load previous playlist: {str(e)}",
                    NotificationType.ERROR
                )
    
    def _load_last_epg(self):
        """Load the last used EPG if available"""
        epg_file = self.db.get_setting('last_epg_file')
        epg_url = self.db.get_setting('last_epg_url')
        
        if epg_url:
            self.window.epg_url_input.setText(epg_url)
            self.load_epg_url()
        elif epg_file and os.path.exists(epg_file):
            try:
                self._load_epg_from_file(epg_file)
                self.window.show_notification(
                    "Previous EPG loaded",
                    NotificationType.SUCCESS
                )
            except Exception as e:
                self.window.show_notification(
                    f"Failed to load previous EPG: {str(e)}",
                    NotificationType.ERROR
                ) 
    
    def show_playlist_manager(self):
        try:
            dialog = PlaylistManagerDialog(self.window)
            
            # Load saved playlists
            saved_playlists = self.db.get_playlists()
            print(f"Loading {len(saved_playlists)} saved playlists")
            dialog.set_playlists(saved_playlists)
            
            # Connect playlist selected signal
            dialog.playlist_selected.connect(lambda path, is_url: self.load_playlist_from_path(path, is_url))
            
            result = dialog.exec()
            
            # Always save playlists when dialog is closed
            playlists = dialog.get_playlists()
            print(f"Attempting to save {len(playlists)} playlists")
            
            if playlists:
                success = self.db.save_playlists(playlists)
                if success:
                    verification = self.db.get_playlists()
                    print(f"Verification: {len(verification)} playlists in database")
                    self.window.show_notification(
                        f"Saved {len(playlists)} playlists successfully",
                        NotificationType.SUCCESS
                    )
                else:
                    self.window.show_notification(
                        "Failed to save playlists",
                        NotificationType.ERROR
                    )
            
            # Only show quit confirmation if we have no channels at all
            if result == QDialog.rejected and not self.playlist.channels:
                response = QMessageBox.question(
                    self.window,
                    "No Playlist",
                    "No playlist is loaded. Would you like to add one?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if response == QMessageBox.StandardButton.Yes:
                    QTimer.singleShot(0, self.show_playlist_manager)
                else:
                    self.window.close()
        except Exception as e:
            self.window.show_notification(
                f"Error showing playlist manager: {str(e)}",
                NotificationType.ERROR
            )
    
    def load_playlist_from_path(self, path: str, is_url: bool):
        logger.debug(f"Loading playlist from {'URL' if is_url else 'path'}: {path}")
        try:
            if is_url:
                logger.debug("Downloading playlist from URL")
                response = requests.get(path)
                response.raise_for_status()
                with tempfile.NamedTemporaryFile(delete=False, suffix='.m3u8') as tmp_file:
                    tmp_file.write(response.content)
                    file_path = tmp_file.name
                    logger.debug(f"Saved URL content to temporary file: {file_path}")
            else:
                file_path = path
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"Playlist file not found: {file_path}")
            
            logger.debug("Parsing playlist file")
            self.playlist = M3UParser.parse(file_path)
            logger.debug(f"Parsed {len(self.playlist.channels)} channels")
            
            self._update_categories()
            self._update_channel_list()
            
            # Save as last used playlist with is_url flag
            logger.debug("Saving playlist settings to database")
            self.db.save_setting('last_playlist', path)  # Save original path/URL, not temporary file
            self.db.save_setting('last_playlist_is_url', 'true' if is_url else 'false')
            
            # Cleanup temporary file if it was a URL download
            if is_url and 'tmp_file' in locals():
                try:
                    os.unlink(file_path)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temporary file: {e}")
            
            self.window.show_notification(
                "Playlist loaded successfully",
                NotificationType.SUCCESS
            )
        except Exception as e:
            logger.error(f"Failed to load playlist: {str(e)}", exc_info=True)
            self.window.show_notification(
                f"Failed to load playlist: {str(e)}",
                NotificationType.ERROR
            ) 