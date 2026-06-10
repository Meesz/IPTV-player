import logging
import os
import sys
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)


class VLCBackend:
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
                vlc_path = "C:\\Program Files\\VideoLAN\\VLC" if is_64bits else "C:\\Program Files (x86)\\VideoLAN\\VLC"
                if not os.path.exists(vlc_path):
                    error_msg = (
                        f"Error: VLC not found in {vlc_path}\n" f"Please install {'64' if is_64bits else '32'}-bit VLC"
                    )
                    return False, error_msg

                os.environ["PATH"] = vlc_path + ";" + os.environ["PATH"]
                os.add_dll_directory(vlc_path)

            # Now try to import VLC
            try:
                import vlc

                cls._vlc = vlc
                # Add some default options?
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
    def get_instance(cls) -> Any:
        """Get the VLC instance."""
        return cls._instance

    @classmethod
    def get_vlc(cls) -> Any:
        """Get the VLC module."""
        return cls._vlc

    @classmethod
    def create_player(cls) -> Any:
        """Create a new media player instance."""
        if not cls._instance:
            raise RuntimeError("VLC not initialized. Call initialize() first.")
        return cls._instance.media_player_new()

    @classmethod
    def bind_video_output(cls, player: Any, window_id: int) -> Optional[str]:
        """Bind VLC video output to a widget and report platform caveats."""
        if not player:
            return "VLC media player is unavailable"

        if sys.platform == "win32":
            player.set_hwnd(window_id)
            return None

        if sys.platform.startswith("linux"):
            session_type = os.environ.get("XDG_SESSION_TYPE", "").strip().lower()
            has_wayland = bool(os.environ.get("WAYLAND_DISPLAY")) or session_type == "wayland"
            display = os.environ.get("DISPLAY", "").strip()
            if has_wayland and not display:
                warning = "Wayland session detected without XWayland; embedded video may be unavailable."
                logger.warning(warning)
                return warning

            player.set_xwindow(int(window_id))
            if has_wayland:
                warning = "Wayland session detected; using XWayland video embedding."
                logger.warning(warning)
                return warning
            return None

        if sys.platform == "darwin":
            player.set_nsobject(int(window_id))
            return None

        warning = f"Unsupported video embedding platform: {sys.platform}"
        logger.warning(warning)
        return warning
