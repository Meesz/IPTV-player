import sys
import logging
from PyQt6.QtWidgets import QApplication
from infra.db.sqlite_connection import SQLiteConnection
from infra.db.playlist_repository import PlaylistRepository
from infra.db.settings_repository import SettingsRepository
from infra.db.favorites_repository import FavoritesRepository
from infra.db.epg_repository import EPGRepository
from core.services.playlist_service import PlaylistService
from core.services.epg_service import EPGService
from core.services.settings_service import SettingsService
from core.services.favorites_service import FavoritesService
from ui.controllers.playlist_controller import PlaylistController
from ui.controllers.epg_controller import EPGController
from ui.controllers.settings_controller import SettingsController
from ui.controllers.main_controller import MainController
from ui.windows.main_window import MainWindow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("iptv_player.log")
    ]
)

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Simple IPTV Player")

    # Infrastructure
    db_connection = SQLiteConnection()
    playlist_repo = PlaylistRepository(db_connection)
    settings_repo = SettingsRepository(db_connection)
    favorites_repo = FavoritesRepository(db_connection)
    epg_repo = EPGRepository(db_connection)

    # Services
    playlist_service = PlaylistService(playlist_repo)
    epg_service = EPGService(epg_repo)
    settings_service = SettingsService(settings_repo)
    favorites_service = FavoritesService(favorites_repo)

    # Controllers
    playlist_controller = PlaylistController(playlist_service)
    epg_controller = EPGController(epg_service)
    settings_controller = SettingsController(settings_service)
    main_controller = MainController(playlist_controller, epg_controller, settings_controller)

    # UI
    window = MainWindow(main_controller, playlist_controller, epg_controller, settings_controller)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
