import logging
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from core.services.epg_service import EPGService
from core.services.favorites_service import FavoritesService
from core.services.history_service import HistoryService
from core.services.playlist_service import PlaylistService
from core.services.settings_service import SettingsService
from infra.db.epg_repository import EPGRepository
from infra.db.favorites_repository import FavoritesRepository
from infra.db.history_repository import HistoryRepository
from infra.db.playlist_repository import PlaylistRepository
from infra.db.settings_repository import SettingsRepository
from infra.db.sqlite_connection import SQLiteConnection
from ui.controllers.epg_controller import EPGController
from ui.controllers.favorites_controller import FavoritesController
from ui.controllers.history_controller import HistoryController
from ui.controllers.main_controller import MainController
from ui.controllers.playlist_controller import PlaylistController
from ui.controllers.settings_controller import SettingsController
from ui.windows.main_window import MainWindow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("iptv_player.log")],
)

logger = logging.getLogger(__name__)


def create_window() -> MainWindow:
    db_connection = SQLiteConnection()
    playlist_repo = PlaylistRepository(db_connection)
    settings_repo = SettingsRepository(db_connection)
    favorites_repo = FavoritesRepository(db_connection)
    history_repo = HistoryRepository(db_connection)
    epg_repo = EPGRepository(db_connection)

    playlist_service = PlaylistService(playlist_repo)
    epg_service = EPGService(epg_repo)
    settings_service = SettingsService(settings_repo)
    favorites_service = FavoritesService(favorites_repo)
    history_service = HistoryService(history_repo)

    playlist_controller = PlaylistController(playlist_service)
    epg_controller = EPGController(epg_service)
    settings_controller = SettingsController(settings_service)
    favorites_controller = FavoritesController(favorites_service)
    history_controller = HistoryController(history_service)
    main_controller = MainController(playlist_controller, settings_controller)

    return MainWindow(
        main_controller,
        playlist_controller,
        epg_controller,
        settings_controller,
        favorites_controller,
        history_controller,
    )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Simple IPTV Player")

    try:
        window = create_window()
    except Exception as exc:
        logger.exception("Application startup failed")
        QMessageBox.critical(
            None,
            "Startup Error",
            f"Failed to start Simple IPTV Player.\n\n{exc}",
        )
        return 1

    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
