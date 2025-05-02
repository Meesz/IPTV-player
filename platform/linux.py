"""Linux-specific platform implementation."""

import os
import sys
import logging
from typing import Optional, Tuple, List

from . import PlatformInterface

logger = logging.getLogger(__name__)


class LinuxPlatform(PlatformInterface):
    """Linux-specific platform implementation."""
    
    VLC_PATHS = [
        "/usr/lib/vlc",
        "/usr/lib64/vlc",
        "/usr/local/lib/vlc"
    ]
    
    def initialize_vlc(self) -> Tuple[bool, Optional[str]]:
        """Initialize VLC for Linux."""
        try:
            # Check if VLC is installed
            vlc_path = self._find_vlc_path()
            if not vlc_path:
                return False, "VLC not found in standard locations"
            
            # Set up environment
            if not self.setup_environment():
                return False, "Failed to set up environment"
            
            # Import VLC
            try:
                import vlc
                return True, None
            except ImportError as e:
                return False, f"Failed to import VLC: {str(e)}"
                
        except Exception as e:
            return False, f"Failed to initialize VLC: {str(e)}"
    
    def get_vlc_paths(self) -> List[str]:
        """Get VLC installation paths for Linux."""
        return self.VLC_PATHS
    
    def setup_environment(self) -> bool:
        """Set up Linux-specific environment variables."""
        try:
            vlc_path = self._find_vlc_path()
            if vlc_path:
                os.environ["LD_LIBRARY_PATH"] = vlc_path + ":" + os.environ.get("LD_LIBRARY_PATH", "")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to set up environment: {str(e)}")
            return False
    
    def get_window_id(self, widget) -> int:
        """Get the window ID for Linux."""
        return int(widget.winId())
    
    def _find_vlc_path(self) -> Optional[str]:
        """Find VLC installation path."""
        for path in self.VLC_PATHS:
            if os.path.exists(path):
                return path
        return None 