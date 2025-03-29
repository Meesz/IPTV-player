"""
This module contains the SettingsController class, 
which is responsible for managing application settings.
"""

import logging
from pathlib import Path
from utils.database import Database


logger = logging.getLogger(__name__)


class SettingsController:
    """Controller for managing application settings."""

    # Default settings values
    DEFAULT_SETTINGS = {
        "volume": "100",
        "auto_reconnect": "true", 
        "max_reconnect_attempts": "5",
        "buffer_size": "1000",
        "sort_channels_by": "name",
        "preferred_quality": "auto",
        "theme": "dark",
        "auto_update_playlist": "false",
        "auto_update_epg": "false",
        "update_interval_hours": "24",
        "cache_expiry_days": "7",
        "pip_width": "320",
        "pip_height": "180",
        "startup_channel": "",
        "enable_hardware_acceleration": "true",
        "enable_debug_logging": "false",
    }

    def __init__(self):
        """Initialize the settings controller.
        
        This creates the database connection and ensures default settings exist.
        """
        # Create database instance
        self.db = Database()
        
        # Initialize default settings
        self._ensure_default_settings()
        
        # Create data directory if it doesn't exist
        self._ensure_data_dir()
        
        # Set up logging based on debug setting
        self._configure_logging()

    def _ensure_default_settings(self):
        """Ensure all default settings exist in the database."""
        for key, value in self.DEFAULT_SETTINGS.items():
            if not self.db.get_setting(key):
                logger.debug(f"Setting default value for {key}: {value}")
                self.db.save_setting(key, value)

    def _ensure_data_dir(self):
        """Ensure the data directory exists."""
        data_dir = Path.home() / ".simple_iptv" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured data directory exists: {data_dir}")
        
        # Create subdirectories
        cache_dir = data_dir / "cache"
        cache_dir.mkdir(exist_ok=True)
        logger.debug(f"Ensured cache directory exists: {cache_dir}")
        
        log_dir = Path.home() / ".simple_iptv" / "logs"
        log_dir.mkdir(exist_ok=True)
        logger.debug(f"Ensured logs directory exists: {log_dir}")

    def _configure_logging(self):
        """Configure logging based on the debug setting."""
        debug_enabled = self.get_setting("enable_debug_logging") == "true"
        log_level = logging.DEBUG if debug_enabled else logging.INFO
        
        # Update root logger level
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        for handler in root_logger.handlers:
            handler.setLevel(log_level)
            
        logger.debug(f"Logging configured with level: {log_level}")

    def save_setting(self, key: str, value: str):
        """Save a setting value.
        
        Args:
            key: The setting key.
            value: The setting value.
        """
        self.db.save_setting(key, value)
        
        # Handle special settings that require immediate action
        if key == "enable_debug_logging":
            self._configure_logging()
            
        logger.debug(f"Saved setting {key}: {value}")

    def get_setting(self, key: str, default: str = None) -> str:
        """Get a setting value.
        
        Args:
            key: The setting key.
            default: Optional default value if not found.
            
        Returns:
            The setting value or default.
        """
        # Use class default if not provided
        if default is None and key in self.DEFAULT_SETTINGS:
            default = self.DEFAULT_SETTINGS[key]
            
        return self.db.get_setting(key, default)

    def get_bool_setting(self, key: str, default: bool = None) -> bool:
        """Get a boolean setting value.
        
        Args:
            key: The setting key.
            default: Optional default value if not found.
            
        Returns:
            The setting value as boolean.
        """
        if default is None and key in self.DEFAULT_SETTINGS:
            default_str = self.DEFAULT_SETTINGS[key]
            default = default_str.lower() == "true"
            
        value = self.get_setting(key, "true" if default else "false")
        return value.lower() == "true"
        
    def get_int_setting(self, key: str, default: int = None) -> int:
        """Get an integer setting value.
        
        Args:
            key: The setting key.
            default: Optional default value if not found.
            
        Returns:
            The setting value as integer.
        """
        if default is None and key in self.DEFAULT_SETTINGS:
            default_str = self.DEFAULT_SETTINGS[key]
            try:
                default = int(default_str)
            except ValueError:
                default = 0
                
        value = self.get_setting(key, str(default) if default is not None else "0")
        try:
            return int(value)
        except ValueError:
            logger.warning(f"Invalid integer setting for {key}: {value}, using default: {default}")
            return default or 0

    def reset_to_defaults(self, keys: list = None):
        """Reset specified settings to their default values.
        
        Args:
            keys: List of keys to reset. If None, reset all settings.
        """
        if keys is None:
            keys = self.DEFAULT_SETTINGS.keys()
            
        for key in keys:
            if key in self.DEFAULT_SETTINGS:
                self.save_setting(key, self.DEFAULT_SETTINGS[key])
                
        logger.info(f"Reset settings to defaults: {keys}")

    def export_settings(self, file_path: str) -> bool:
        """Export all settings to a file.
        
        Args:
            file_path: Path to save settings to.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            settings = {}
            for key in self.DEFAULT_SETTINGS.keys():
                settings[key] = self.get_setting(key)
                
            with open(file_path, 'w') as f:
                for key, value in settings.items():
                    f.write(f"{key}={value}\n")
                    
            logger.info(f"Exported settings to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export settings: {e}")
            return False

    def import_settings(self, file_path: str) -> bool:
        """Import settings from a file.
        
        Args:
            file_path: Path to load settings from.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line:
                        key, value = line.split('=', 1)
                        if key in self.DEFAULT_SETTINGS:
                            self.save_setting(key, value)
                            
            logger.info(f"Imported settings from {file_path}")
            self._configure_logging()  # Reconfigure logging in case it changed
            return True
        except Exception as e:
            logger.error(f"Failed to import settings: {e}")
            return False

    def clear_setting(self, key: str):
        """Remove a setting from the database.

        Args:
            key (str): The setting key to remove
        """
        self.db.clear_setting(key)
