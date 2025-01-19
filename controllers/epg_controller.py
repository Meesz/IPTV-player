"""
This module contains the EPGController class, 
which is responsible for loading and displaying the EPG data.
"""

from datetime import datetime
import tempfile
import requests
import os

# pylint: disable=no-name-in-module
from PyQt6.QtCore import QTimer, QThreadPool
from utils.epg_parser import EPGParser
from views.notification import NotificationType
from utils.worker import Worker


class EPGController:
    """Controller for managing EPG data and updating the UI."""

    def __init__(self, main_window, settings_controller):
        self.window = main_window
        self.settings = settings_controller
        self.epg_guide = None
        self.threadpool = QThreadPool()

        # Create timer for EPG updates
        self.epg_timer = QTimer()
        self.epg_timer.setInterval(60000)  # Update every minute
        self.epg_timer.timeout.connect(self._update_epg_display)

    def load_epg_from_file(self, file_path: str) -> None:
        """Load EPG data from a file."""
        self.window.show_notification("Loading EPG data...", NotificationType.INFO)
        
        worker = Worker(self._load_epg_worker, file_path)
        worker.signals.result.connect(self._on_epg_loaded)
        worker.signals.error.connect(self._on_epg_error)
        
        self.threadpool.start(worker)

    def load_epg_from_url(self, url: str) -> None:
        """Load EPG data from a URL."""
        self.window.show_notification("Downloading EPG data...", NotificationType.INFO)
        
        worker = Worker(self._download_epg_worker, url)
        worker.signals.result.connect(self._on_epg_loaded)
        worker.signals.error.connect(self._on_epg_error)
        
        self.threadpool.start(worker)

    def _load_epg_worker(self, file_path: str) -> tuple:
        """Worker function to load EPG in background."""
        try:
            epg_guide = EPGParser.parse_xmltv(file_path)
            return (True, epg_guide, file_path)
        except Exception as e:
            return (False, str(e), None)

    def _download_epg_worker(self, url: str) -> tuple:
        """Worker function to download and load EPG in background."""
        tmp_path = None
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp_file:
                tmp_file.write(response.content)
                tmp_path = tmp_file.name

            epg_guide = EPGParser.parse_xmltv(tmp_path)
            return (True, epg_guide, url)

        except Exception as e:
            return (False, str(e), None)

        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception as e:
                    print(f"Failed to cleanup temporary file: {e}")

    def _on_epg_loaded(self, result):
        """Handle successful EPG loading."""
        success, data, path = result
        
        if success:
            self.epg_guide = data
            self.settings.save_setting("last_epg", path)
            self._update_epg_display()
            self.window.show_notification(
                "EPG data loaded successfully", 
                NotificationType.SUCCESS
            )
        else:
            self.window.show_notification(
                f"Failed to load EPG: {data}", 
                NotificationType.ERROR
            )

    def _on_epg_error(self, error_info):
        """Handle EPG loading error."""
        error, _ = error_info
        self.window.show_notification(
            f"Error loading EPG: {str(error)}", 
            NotificationType.ERROR
        )

    def _update_epg_display(self):
        """Update the EPG display for the current channel."""
        if not self.epg_guide or not self.window.current_channel:
            return

        channel_data = self.epg_guide.get_channel_data(
            self.window.current_channel.epg_id
        )
        if not channel_data:
            return

        current_time = datetime.now()
        current_program = channel_data.get_current_program(current_time)

        if current_program:
            time_str = (
                f"{current_program.start_time.strftime('%H:%M')} - "
                f"{current_program.end_time.strftime('%H:%M')}"
            )
            self.window.epg_widget.update_current_program(
                current_program.title, time_str, current_program.description
            )

            # Get upcoming programs
            upcoming = [
                p for p in channel_data.programs if p.start_time > current_time
            ][:5]
            self.window.epg_widget.set_upcoming_programs(upcoming)

    def refresh_epg(self):
        """Update the EPG display with current program information."""
        self._update_epg_display()
