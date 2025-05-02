"""Module for managing VLC initialization and configuration."""

import os
import sys
import logging
import time
import subprocess
from typing import Optional, Tuple, List, Dict
from enum import Enum, auto

logger = logging.getLogger(__name__)


class VLCInitError(Exception):
    """Custom exception for VLC initialization errors."""
    pass


class VLCInitStatus(Enum):
    """Status of VLC initialization."""
    SUCCESS = auto()
    NOT_FOUND = auto()
    IMPORT_ERROR = auto()
    VERSION_MISMATCH = auto()
    PERMISSION_ERROR = auto()
    UNKNOWN_ERROR = auto()


class VLCManager:
    """Manages VLC initialization and provides a clean interface for media playback."""

    _instance = None
    _vlc = None
    _init_status: VLCInitStatus = None
    _init_error: Optional[str] = None
    _max_retries = 3
    _retry_delay = 2  # seconds

    # Common VLC installation paths
    VLC_PATHS = {
        "win32": [
            "C:\\Program Files\\VideoLAN\\VLC",
            "C:\\Program Files (x86)\\VideoLAN\\VLC"
        ],
        "linux": [
            "/usr/lib/vlc",
            "/usr/lib64/vlc",
            "/usr/local/lib/vlc"
        ],
        "darwin": [
            "/Applications/VLC.app/Contents/MacOS/lib"
        ]
    }

    @classmethod
    def initialize(cls, retries: int = None) -> Tuple[bool, Optional[str]]:
        """Initialize VLC environment before application starts.
        
        Args:
            retries: Number of initialization attempts. If None, uses default.
            
        Returns:
            Tuple of (success, error_message)
        """
        if retries is not None:
            cls._max_retries = retries

        for attempt in range(cls._max_retries):
            try:
                logger.info(f"VLC initialization attempt {attempt + 1}/{cls._max_retries}")
                
                # Check platform-specific requirements
                if not cls._check_platform_requirements():
                    continue

                # Try to import VLC
                if not cls._import_vlc():
                    continue

                # Create VLC instance
                if not cls._create_instance():
                    continue

                cls._init_status = VLCInitStatus.SUCCESS
                return True, None

            except Exception as e:
                error_msg = f"VLC initialization attempt {attempt + 1} failed: {str(e)}"
                logger.error(error_msg)
                cls._init_error = error_msg
                
                if attempt < cls._max_retries - 1:
                    time.sleep(cls._retry_delay)
                else:
                    cls._init_status = VLCInitStatus.UNKNOWN_ERROR
                    return False, error_msg

        return False, cls._init_error

    @classmethod
    def _check_platform_requirements(cls) -> bool:
        """Check platform-specific requirements for VLC."""
        try:
            if sys.platform == "win32":
                return cls._check_windows_requirements()
            elif sys.platform.startswith("linux"):
                return cls._check_linux_requirements()
            elif sys.platform == "darwin":
                return cls._check_macos_requirements()
            else:
                logger.warning(f"Unsupported platform: {sys.platform}")
                return False
        except Exception as e:
            logger.error(f"Platform check failed: {str(e)}")
            return False

    @classmethod
    def _check_windows_requirements(cls) -> bool:
        """Check Windows-specific requirements."""
        is_64bits = sys.maxsize > 2**32
        for vlc_path in cls.VLC_PATHS["win32"]:
            if os.path.exists(vlc_path):
                os.environ["PATH"] = vlc_path + ";" + os.environ["PATH"]
                os.add_dll_directory(vlc_path)
                return True
        return False

    @classmethod
    def _check_linux_requirements(cls) -> bool:
        """Check Linux-specific requirements."""
        for vlc_path in cls.VLC_PATHS["linux"]:
            if os.path.exists(vlc_path):
                return True
        return False

    @classmethod
    def _check_macos_requirements(cls) -> bool:
        """Check macOS-specific requirements."""
        for vlc_path in cls.VLC_PATHS["darwin"]:
            if os.path.exists(vlc_path):
                return True
        return False

    @classmethod
    def _import_vlc(cls) -> bool:
        """Attempt to import the VLC module."""
        try:
            import vlc
            cls._vlc = vlc
            return True
        except ImportError as e:
            logger.error(f"Failed to import VLC: {str(e)}")
            cls._init_status = VLCInitStatus.IMPORT_ERROR
            return False

    @classmethod
    def _create_instance(cls) -> bool:
        """Create a VLC instance."""
        try:
            cls._instance = cls._vlc.Instance()
            return True
        except Exception as e:
            logger.error(f"Failed to create VLC instance: {str(e)}")
            return False

    @classmethod
    def get_instance(cls):
        """Get the VLC instance."""
        if not cls._instance:
            raise VLCInitError("VLC not initialized. Call initialize() first.")
        return cls._instance

    @classmethod
    def get_vlc(cls):
        """Get the VLC module."""
        if not cls._vlc:
            raise VLCInitError("VLC not initialized. Call initialize() first.")
        return cls._vlc

    @classmethod
    def create_player(cls):
        """Create a new media player instance."""
        if not cls._instance:
            raise VLCInitError("VLC not initialized. Call initialize() first.")
        return cls._instance.media_player_new()

    @classmethod
    def get_init_status(cls) -> VLCInitStatus:
        """Get the initialization status."""
        return cls._init_status

    @classmethod
    def get_init_error(cls) -> Optional[str]:
        """Get the initialization error message."""
        return cls._init_error
