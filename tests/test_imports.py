import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    from core.models import Channel, Playlist, Settings
    print("Core models imported")
    
    from core.services.playlist_service import PlaylistService
    print("PlaylistService imported")
    
    from infra.db.sqlite_connection import SQLiteConnection
    print("SQLiteConnection imported")
    
    from infra.parsers.m3u_parser import M3UParser
    print("M3UParser imported")
    
    from ui.controllers.main_controller import MainController
    print("MainController imported")
    
    print("All imports successful")
except Exception as e:
    print(f"Import failed: {e}")
    sys.exit(1)
