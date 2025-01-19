"""
Main application entry point.
"""

import sys
import logging

# pylint: disable=no-name-in-module
from PyQt6.QtWidgets import QApplication, QMessageBox
from views.main_window import MainWindow
from views.vlc_manager import VLCManager
from controllers.player_controller import PlayerController
from views.playlist_manager import PlaylistManagerDialog
from controllers.settings_controller import SettingsController
from controllers.playlist_controller import PlaylistController


# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main application entry point."""
    logger.debug("Starting application")
    app = QApplication(sys.argv)

    # Initialize VLC before creating any widgets
    success, error = VLCManager.initialize()
    if not success:
        QMessageBox.critical(None, "Error", f"Failed to initialize VLC:\n{error}")
        return 1

    # Create controllers first
    settings_controller = SettingsController()
    
    # Show playlist manager first
    playlist_manager = PlaylistManagerDialog()
    
    # Load playlists from settings database
    saved_playlists = settings_controller.db.get_playlists()
    playlist_manager.set_playlists(saved_playlists)
    
    result = playlist_manager.exec()
    
    # If user selected a playlist (accepted dialog)
    if result == PlaylistManagerDialog.DialogCode.Accepted:
        selected_playlist = playlist_manager.get_selected_playlist()
        if selected_playlist:
            # Create main window
            main_window = MainWindow()
            
            # Initialize remaining controllers
            playlist_controller = PlaylistController(main_window, settings_controller)
            player_controller = PlayerController(main_window)
            
            # Set controllers in main window
            main_window.player_controller = player_controller
            main_window.playlist_controller = playlist_controller
            
            # Load the selected playlist
            playlist_controller.load_playlist_from_path(
                selected_playlist['path'], 
                selected_playlist['is_url']
            )
            
            # Save playlists before showing main window
            playlists = playlist_manager.get_playlists()
            if playlists:
                settings_controller.db.save_playlists(playlists)
            
            main_window.show()
            return app.exec()
    
    # If no playlist selected, exit application
    return 0


if __name__ == "__main__":
    main()
