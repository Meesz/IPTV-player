"""
Main application entry point.
"""

import sys
import logging

# pylint: disable=no-name-in-module
from PyQt6.QtWidgets import QApplication, QMessageBox
from views.main_window import MainWindow
from core.container import Container
from platform import PlatformFactory

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main application entry point."""
    logger.debug("Starting application")
    app = QApplication(sys.argv)

    try:
        # Initialize platform
        platform = PlatformFactory.create_platform()
        success, error = platform.initialize_vlc()
        if not success:
            QMessageBox.critical(None, "Error", f"Failed to initialize VLC:\n{error}")
            return 1

        # Create main window
        logger.debug("Creating main window")
        main_window = MainWindow()

        # Initialize container and get player controller
        container = Container()
        player_controller = container.get_player_controller(main_window)
        main_window.player_controller = player_controller

        # Show the main window
        main_window.show()

        # Show playlist manager if needed
        if not player_controller.playlist.channels:
            logger.debug("No channels found, showing playlist manager")
            player_controller.show_playlist_manager()

        # Run application
        exit_code = app.exec()

        # Cleanup
        container.cleanup()

        return exit_code

    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        QMessageBox.critical(None, "Error", f"Application error:\n{str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
