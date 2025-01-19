"""
Central configuration for the Simple IPTV application.
"""

from pathlib import Path
import logging


class Config:
    """Central configuration class for the application."""

    # Application info
    APP_NAME = "Simple IPTV"
    APP_VERSION = "1.0.0"

    # Paths
    BASE_DIR = Path(__file__).parent
    CACHE_DIR = BASE_DIR / "cache"
    DATABASE_PATH = BASE_DIR / "data" / "database.db"

    # Create necessary directories
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Network settings
    REQUEST_TIMEOUT = 30  # seconds
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds

    # UI settings
    NOTIFICATION_DURATION = 3000  # milliseconds
    SEARCH_DEBOUNCE_DELAY = 300  # milliseconds
    CHANNEL_LIST_BATCH_SIZE = 10000
    PROGRESS_UPDATE_INTERVAL = 50000  # channels

    # Player settings
    DEFAULT_VOLUME = 100
    VOLUME_STEP = 5
    EPG_UPDATE_INTERVAL = 60000  # milliseconds (1 minute)

    # Cache settings
    PLAYLIST_CACHE_DURATION = 3600  # seconds (1 hour)
    EPG_CACHE_DURATION = 3600 * 12  # seconds (12 hours)

    # File patterns
    PLAYLIST_EXTENSIONS = [".m3u", ".m3u8"]
    EPG_EXTENSIONS = [".xml", ".xmltv"]

    # Default values
    DEFAULT_CATEGORY = "All"
    UNCATEGORIZED_LABEL = "Uncategorized"

    # Logging settings
    LOG_LEVEL = logging.DEBUG
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    # Database settings
    DB_MAX_CONNECTIONS = 5
    DB_TIMEOUT = 5  # seconds
    DB_RETRY_ATTEMPTS = 3
    DB_RETRY_DELAY = 0.1  # seconds

    @classmethod
    def get_cache_path(cls, filename: str) -> Path:
        """Get the full path for a cache file."""
        return cls.CACHE_DIR / filename

    @classmethod
    def is_valid_playlist_file(cls, filename: str) -> bool:
        """Check if the file has a valid playlist extension."""
        return any(filename.lower().endswith(ext) for ext in cls.PLAYLIST_EXTENSIONS)

    @classmethod
    def is_valid_epg_file(cls, filename: str) -> bool:
        """Check if the file has a valid EPG extension."""
        return any(filename.lower().endswith(ext) for ext in cls.EPG_EXTENSIONS)
