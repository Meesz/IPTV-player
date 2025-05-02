"""Platform-specific implementations and abstractions."""

from typing import Protocol, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class PlatformInterface(Protocol):
    """Interface for platform-specific implementations."""
    
    def initialize_vlc(self) -> Tuple[bool, Optional[str]]:
        """Initialize VLC for the specific platform."""
        ...
    
    def get_vlc_paths(self) -> list[str]:
        """Get VLC installation paths for the platform."""
        ...
    
    def setup_environment(self) -> bool:
        """Set up platform-specific environment variables."""
        ...
    
    def get_window_id(self, widget) -> int:
        """Get the window ID for the platform."""
        ...


class PlatformFactory:
    """Factory for creating platform-specific implementations."""
    
    @staticmethod
    def create_platform() -> PlatformInterface:
        """Create the appropriate platform implementation."""
        import sys
        
        if sys.platform == "win32":
            from .windows import WindowsPlatform
            return WindowsPlatform()
        elif sys.platform.startswith("linux"):
            from .linux import LinuxPlatform
            return LinuxPlatform()
        elif sys.platform == "darwin":
            from .macos import MacOSPlatform
            return MacOSPlatform()
        else:
            raise NotImplementedError(f"Platform {sys.platform} not supported") 