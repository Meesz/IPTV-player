"""
Main application entry point.
"""

import sys
import logging
from pathlib import Path
from typing import Tuple

# pylint: disable=no-name-in-module
from PyQt6.QtWidgets import QApplication, QMessageBox
from views.main_window import MainWindow
from views.vlc_manager import VLCManager
from controllers.player_controller import PlayerController
from views.playlist_manager import PlaylistManagerDialog
from controllers.settings_controller import SettingsController
from controllers.playlist_controller import PlaylistController
from config import Config


def setup_logging() -> None:
    """Configure application logging."""
    log_file = Config.BASE_DIR / "logs" / "app.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=Config.LOG_LEVEL,
        format=Config.LOG_FORMAT,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )


def initialize_vlc() -> Tuple[bool, str]:
    """Initialize VLC and return status."""
    logger = logging.getLogger(__name__)
    logger.debug("Initializing VLC...")
    
    try:
        success, error = VLCManager.initialize()
        if not success:
            logger.error(f"VLC initialization failed: {error}")
        return success, error
    except Exception as e:
        logger.exception("Unexpected error during VLC initialization")
        return False, str(e)


def load_initial_playlist(
    playlist_controller: PlaylistController,
    settings_controller: SettingsController
) -> bool:
    """Load initial playlist from playlist manager."""
    logger = logging.getLogger(__name__)
    
    try:
        # Show playlist manager
        playlist_manager = PlaylistManagerDialog()
        
        # Load playlists from settings database
        saved_playlists = settings_controller.db.get_playlists()
        playlist_manager.set_playlists(saved_playlists)
        
        result = playlist_manager.exec()
        
        # Handle playlist selection
        if result == PlaylistManagerDialog.DialogCode.Accepted:
            selected_playlist = playlist_manager.get_selected_playlist()
            if selected_playlist:
                # Save playlists before proceeding
                playlists = playlist_manager.get_playlists()
                if playlists:
                    settings_controller.db.save_playlists(playlists)
                return True, selected_playlist
                
        return False, None
        
    except Exception as e:
        logger.exception("Error loading initial playlist")
        return False, None


def main() -> int:
    """
    Main application entry point.
    
    Returns:
        int: Application exit code
    """
    # Setup logging first
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info(f"Starting {Config.APP_NAME} v{Config.APP_VERSION}")

    # Create application instance
    app = QApplication(sys.argv)
    app.setApplicationName(Config.APP_NAME)
    app.setApplicationVersion(Config.APP_VERSION)

    try:
        # Initialize VLC
        vlc_success, vlc_error = initialize_vlc()
        if not vlc_success:
            QMessageBox.critical(None, "Error", f"Failed to initialize VLC:\n{vlc_error}")
            return 1

        # Create controllers
        settings_controller = SettingsController()
        
        # Load initial playlist
        playlist_success, selected_playlist = load_initial_playlist(
            None,  # playlist_controller not created yet
            settings_controller
        )
        
        if not playlist_success:
            logger.info("No playlist selected, exiting")
            return 0
            
        # Create main window and remaining controllers
        main_window = MainWindow()
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
        
        # Show main window and start event loop
        main_window.show()
        return app.exec()

    except Exception as e:
        logger.exception("Unhandled exception in main")
        QMessageBox.critical(None, "Error", f"An unexpected error occurred:\n{str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
