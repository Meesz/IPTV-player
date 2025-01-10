from utils.database import Database

class SettingsController:
    """Controller for managing application settings."""
    
    def __init__(self):
        """Initialize the settings controller with database connection."""
        self.db = Database()
        
    def save_setting(self, key: str, value: str):
        """Save a setting to the database.
        
        Args:
            key (str): The setting key
            value (str): The setting value
        """
        self.db.save_setting(key, value)
        
    def get_setting(self, key: str, default: str = "") -> str:
        """Get a setting from the database.
        
        Args:
            key (str): The setting key
            default (str): Default value if setting doesn't exist
            
        Returns:
            str: The setting value or default if not found
        """
        return self.db.get_setting(key, default)
        
    def clear_setting(self, key: str):
        """Remove a setting from the database.
        
        Args:
            key (str): The setting key to remove
        """
        self.db.clear_setting(key) 