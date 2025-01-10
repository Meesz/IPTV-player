"""
This module contains the EPGController class, 
which is responsible for loading and displaying the EPG data.
"""

from datetime import datetime
import tempfile
import requests

# pylint: disable=no-name-in-module
from PyQt6.QtCore import QTimer
from utils.epg_parser import EPGParser
from views.notification import NotificationType


class EPGController:
    """Controller for managing EPG data and updating the UI."""

    def __init__(self, main_window, settings_controller):
        self.window = main_window
        self.settings = settings_controller
        self.epg_guide = None

        # Create timer for EPG updates
        self.epg_timer = QTimer()
        self.epg_timer.setInterval(60000)  # Update every minute
        self.epg_timer.timeout.connect(self._update_epg_display)

    def load_epg_from_file(self, file_path: str) -> bool:
        """Load EPG data from a file."""
        try:
            self.epg_guide = EPGParser.parse_xmltv(file_path)
            self._update_epg_display()
            self.epg_timer.start()
            self.settings.save_setting("last_epg", file_path)
            return True
        except Exception as e:
            self.window.show_notification(
                f"Failed to parse EPG: {str(e)}", NotificationType.ERROR
            )
            return False

    def load_epg_from_url(self, url: str) -> bool:
        """Load EPG data from a URL."""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp_file:
                tmp_file.write(response.content)
                success = self.load_epg_from_file(tmp_file.name)

            if success:
                self.settings.save_setting("last_epg_url", url)
            return success

        except Exception as e:
            self.window.show_notification(
                f"Failed to download EPG: {str(e)}", NotificationType.ERROR
            )
            return False

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
