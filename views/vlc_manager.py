"""Module for managing VLC initialization and configuration."""

import os
import sys
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class VLCManager:
    """Manages VLC initialization and provides a clean interface for media playback."""

    _instance = None
    _vlc = None

    @classmethod
    def initialize(cls) -> Tuple[bool, Optional[str]]:
        """Initialize VLC environment before application starts."""
        try:
            # Try to determine Python architecture
            is_64bits = sys.maxsize > 2**32

            # Set up Windows environment first
            if sys.platform == "win32":
                vlc_path = (
                    "C:\\Program Files\\VideoLAN\\VLC"
                    if is_64bits
                    else "C:\\Program Files (x86)\\VideoLAN\\VLC"
                )
                if not os.path.exists(vlc_path):
                    error_msg = (
                        f"Error: VLC not found in {vlc_path}\n"
                        f"Please install {'64' if is_64bits else '32'}-bit VLC"
                    )
                    return False, error_msg

                os.environ["PATH"] = vlc_path + ";" + os.environ["PATH"]
                os.add_dll_directory(vlc_path)

            # Now try to import VLC
            try:
                # pylint: disable=import-outside-toplevel
                import vlc

                cls._vlc = vlc
                cls._instance = cls._vlc.Instance()
                return True, None
            except ImportError as e:
                error_msg = f"Failed to import VLC: {str(e)}"
                logger.error(error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"Failed to initialize VLC: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    @classmethod
    def get_instance(cls):
        """Get the VLC instance."""
        return cls._instance

    @classmethod
    def get_vlc(cls):
        """Get the VLC module."""
        return cls._vlc

    @classmethod
    def create_player(cls):
        """Create a new media player instance."""
        if not cls._instance:
            raise RuntimeError("VLC not initialized. Call initialize() first.")
        return cls._instance.media_player_new()
