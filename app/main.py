import logging
import os
import sys
from collections.abc import MutableMapping
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt6.QtCore import QtMsgType, qInstallMessageHandler
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QMessageBox

from core.redaction import RedactingFormatter
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


def _resolve_log_level() -> int:
    raw_level = os.getenv("IPTV_LOG_LEVEL", "INFO").strip().upper()
    return getattr(logging, raw_level, logging.INFO)


LOG_FILE_NAME = "iptv_player.log"
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 2

logger = logging.getLogger(__name__)
qt_logger = logging.getLogger("qt")

_QT_LOG_LEVELS = {
    QtMsgType.QtDebugMsg: logging.DEBUG,
    QtMsgType.QtInfoMsg: logging.INFO,
    QtMsgType.QtWarningMsg: logging.WARNING,
    QtMsgType.QtCriticalMsg: logging.ERROR,
    QtMsgType.QtFatalMsg: logging.CRITICAL,
}


def default_log_path() -> Path:
    """Log file inside the app data directory (the same one the database uses)."""
    return Path.home() / ".simple_iptv" / LOG_FILE_NAME


def configure_logging(log_path: Path | None = None) -> list[logging.Handler]:
    """Log to the console and a rotating file; `log_path` overrides the default location.

    The console handler is always installed. A missing log directory is created with mode
    0o700 (an existing one is left alone). If the log file cannot be set up (unwritable
    directory, no home directory), file logging is skipped with a warning and the app
    keeps logging to the console only. Returns the handlers that were installed.
    """
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    file_error: Exception | None = None
    try:
        path = log_path if log_path is not None else default_log_path()
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8")
        )
    except (OSError, RuntimeError) as exc:
        file_error = exc
    # Tracebacks of chained requests errors can echo Xtream query passwords.
    formatter = RedactingFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    for handler in handlers:
        handler.setFormatter(formatter)
    logging.basicConfig(level=_resolve_log_level(), handlers=handlers)
    if file_error is not None:
        logger.warning("File logging disabled: could not set up log file: %s", file_error)
    logger.info("=== Session start (pid %s, Python %s) ===", os.getpid(), sys.version.split()[0])
    return handlers


def prefer_xcb_on_wayland(env: MutableMapping[str, str], platform: str = sys.platform) -> bool:
    """Request the xcb (XWayland) Qt platform on Linux Wayland sessions so VLC can embed video.

    VLC can only draw into an X11 window id. Does nothing unless `QT_QPA_PLATFORM` is unset or
    empty, a Wayland session is detected and `DISPLAY` is set. Returns True if `env` was changed.
    """
    if not platform.startswith("linux") or env.get("QT_QPA_PLATFORM", "").strip():
        return False
    is_wayland = bool(env.get("WAYLAND_DISPLAY")) or env.get("XDG_SESSION_TYPE", "").strip().lower() == "wayland"
    if not is_wayland or not env.get("DISPLAY", "").strip():
        return False
    env["QT_QPA_PLATFORM"] = "xcb;wayland"
    return True


def _forward_qt_message(msg_type, _context, message: str) -> None:
    qt_logger.log(_QT_LOG_LEVELS.get(msg_type, logging.WARNING), message)


def _show_critical_dialog(title: str, message: str) -> None:
    QMessageBox.critical(None, title, message)


def _install_exception_hook() -> None:
    default_hook = sys.excepthook

    def _handle_exception(exc_type, exc_value, exc_traceback) -> None:
        logger.exception(
            "Unhandled application error",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        _show_critical_dialog(
            "Application Error",
            f"Simple IPTV Player hit an unexpected error.\n\n{exc_value}",
        )
        default_hook(exc_type, exc_value, exc_traceback)

    sys.excepthook = _handle_exception


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
    configure_logging()
    qInstallMessageHandler(_forward_qt_message)
    if prefer_xcb_on_wayland(os.environ):
        logger.info("Wayland session detected; requesting Qt platform 'xcb;wayland' for embedded video")
    app = QApplication(sys.argv)
    logger.info("Qt platform: %s", QGuiApplication.platformName())
    app.setApplicationName("Simple IPTV Player")
    _install_exception_hook()

    try:
        window = create_window()
    except Exception as exc:
        logger.exception("Application startup failed")
        _show_critical_dialog("Startup Error", f"Failed to start Simple IPTV Player.\n\n{exc}")
        return 1

    if not window.right_panel.player_widget.vlc_available:
        _show_critical_dialog(
            "VLC Unavailable",
            "Playback will be unavailable until VLC is installed and importable.\n\n"
            f"{window.right_panel.player_widget.placeholder.text()}",
        )

    window.show()
    exit_code = app.exec()
    logger.info("=== Session end (exit code %s) ===", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
