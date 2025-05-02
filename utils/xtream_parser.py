"""
This module contains the XTREAMParser class, 
which is responsible for parsing XTREAM service playlists.
"""

import logging
import requests
from requests.exceptions import RequestException
from models.playlist import Playlist, Channel

# Configure logger
logger = logging.getLogger(__name__)

class XTREAMParser:
    """Parser for XTREAM service playlists."""
    
    def __init__(self, base_url: str, username: str, password: str):
        """Initialize the XTREAM parser.
        
        Args:
            base_url: The base URL of the XTREAM service
            username: The username for authentication
            password: The password for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.session = requests.Session()
        
    def authenticate(self) -> bool:
        """Authenticate with the XTREAM service.
        
        Returns:
            bool: True if authentication succeeded, False otherwise
        """
        try:
            url = f"{self.base_url}/player_api.php"
            params = {
                "username": self.username,
                "password": self.password,
                "action": "get_live_categories"
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # Check if authentication was successful
            if response.status_code == 200:
                logger.info("Successfully authenticated with XTREAM service")
                return True
            else:
                logger.error(f"Authentication failed with status code: {response.status_code}")
                return False
                
        except RequestException as e:
            logger.error(f"Authentication error: {str(e)}")
            return False
            
    def get_categories(self) -> list:
        """Get available categories from the XTREAM service.
        
        Returns:
            list: List of category dictionaries
        """
        try:
            url = f"{self.base_url}/player_api.php"
            params = {
                "username": self.username,
                "password": self.password,
                "action": "get_live_categories"
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except RequestException as e:
            logger.error(f"Error getting categories: {str(e)}")
            return []
            
    def get_channels(self, category_id: str) -> list:
        """Get channels for a specific category.
        
        Args:
            category_id: The ID of the category
            
        Returns:
            list: List of channel dictionaries
        """
        try:
            url = f"{self.base_url}/player_api.php"
            params = {
                "username": self.username,
                "password": self.password,
                "action": "get_live_streams",
                "category_id": category_id
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except RequestException as e:
            logger.error(f"Error getting channels for category {category_id}: {str(e)}")
            return []
            
    def parse(self) -> Playlist:
        """Parse the XTREAM playlist.
        
        Returns:
            Playlist: The parsed playlist object
        """
        # Authenticate first
        if not self.authenticate():
            raise RuntimeError("Failed to authenticate with XTREAM service")
            
        # Create new playlist
        playlist = Playlist()
        
        # Get categories
        categories = self.get_categories()
        logger.info(f"Found {len(categories)} categories")
        
        # Get channels for each category
        for category in categories:
            category_id = category.get("category_id")
            category_name = category.get("category_name", "Unknown")
            
            channels = self.get_channels(category_id)
            logger.info(f"Found {len(channels)} channels in category {category_name}")
            
            # Create channel objects
            for channel_data in channels:
                channel = Channel(
                    name=channel_data.get("name", "Unknown"),
                    url=f"{self.base_url}/live/{self.username}/{self.password}/{channel_data.get('stream_id')}.ts",
                    group=category_name,
                    logo=channel_data.get("stream_icon", "")
                )
                playlist.add_channel(channel)
                
        return playlist 