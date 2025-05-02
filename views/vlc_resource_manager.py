"""Module for managing VLC resources with context manager support."""

import logging

logger = logging.getLogger(__name__)


class VLCResourceManager:
    """Context manager for VLC resources."""
    
    def __init__(self, player=None, instance=None):
        self.player = player
        self.instance = instance
        self._released = False
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        
    def release(self):
        """Release VLC resources."""
        if self._released:
            return
            
        try:
            if self.player:
                self.player.stop()
                self.player.release()
                self.player = None
                
            if self.instance:
                self.instance.release()
                self.instance = None
                
            self._released = True
        except Exception as e:
            logger.error(f"Error releasing VLC resources: {str(e)}") 