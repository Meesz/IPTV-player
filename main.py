import sys
import logging
from PyQt6.QtWidgets import QApplication
from views.main_window import MainWindow
from controllers.player_controller import PlayerController

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    logger.debug("Starting application")
    app = QApplication(sys.argv)

    # Create main window and controller
    logger.debug("Creating main window")
    main_window = MainWindow()
    logger.debug("Creating player controller")
    controller = PlayerController(main_window)

    # Show the main window
    main_window.show()

    # Show playlist manager if needed
    if not controller.playlist.channels:
        logger.debug("No channels found, showing playlist manager")
        controller.show_playlist_manager()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
