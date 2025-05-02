"""Dependency injection container for the application."""

from typing import Dict, Any, Type, Optional
import logging
from functools import lru_cache

from platform import PlatformFactory
from views.vlc_manager import VLCManager
from controllers.player_controller import PlayerController
from controllers.playlist_controller import PlaylistController
from controllers.epg_controller import EPGController
from controllers.settings_controller import SettingsController
from models.playlist import Playlist

logger = logging.getLogger(__name__)


class Container:
    """Dependency injection container."""
    
    _instance: Optional['Container'] = None
    _services: Dict[Type, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._services:
            self._initialize_services()
    
    def _initialize_services(self):
        """Initialize core services."""
        # Platform services
        self._services[PlatformFactory] = PlatformFactory()
        
        # Core services
        self._services[VLCManager] = VLCManager()
        self._services[SettingsController] = SettingsController()
        
        # Data services
        self._services[Playlist] = Playlist()
    
    def register(self, service_type: Type, service: Any):
        """Register a service with the container."""
        self._services[service_type] = service
    
    def get(self, service_type: Type) -> Any:
        """Get a service from the container."""
        if service_type not in self._services:
            raise KeyError(f"Service {service_type.__name__} not registered")
        return self._services[service_type]
    
    @lru_cache
    def get_player_controller(self, main_window) -> PlayerController:
        """Get the player controller with dependencies."""
        settings = self.get(SettingsController)
        playlist = self.get(Playlist)
        
        playlist_controller = PlaylistController(main_window, settings)
        epg_controller = EPGController(config={'window': main_window, 'settings': settings})
        
        return PlayerController(
            main_window=main_window,
            settings=settings,
            playlist_controller=playlist_controller,
            epg_controller=epg_controller
        )
    
    def cleanup(self):
        """Clean up all services and resources."""
        try:
            # Clean up VLC resources first
            if VLCManager in self._services:
                vlc_manager = self._services[VLCManager]
                if hasattr(vlc_manager, 'cleanup'):
                    vlc_manager.cleanup()
            
            # Clear all services
            self._services.clear()
            
        except Exception as e:
            logger.error(f"Error during container cleanup: {str(e)}")
        self.get_player_controller.cache_clear() 