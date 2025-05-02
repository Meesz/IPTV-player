# Simple IPTV Player System Structure

This document provides an overview of the system structure and key components of the Simple IPTV Player application.

## Core Components

### Controllers
- `player_controller.py`: Manages channel playback, favorites, and playlist interactions
- `settings_controller.py`: Handles application settings and configuration
- `playlist_controller.py`: Manages playlist loading and channel organization
- `epg_controller.py`: Handles Electronic Program Guide data

### Views
- `main_window.py`: Main application window and UI layout
- `left_panel.py`: Channel list and category selection
- `right_panel.py`: Player and EPG display
- `menu_bar.py`: Application menu and actions
- `search_bar.py`: Channel search functionality
- `notification.py`: System notifications

### Models
- `playlist.py`: Channel and playlist data structures
- `epg.py`: EPG data structures

### Utils
- `m3u_parser.py`: M3U playlist file parsing
- `database.py`: Local storage and settings persistence
- `themes.py`: UI theming system
- `styles.py`: UI styling components

### Playback
- `manager.py`: Video playback management
- `player.py`: Core video player implementation

## Data Flow

1. Playlist Loading:
   - User selects playlist through `playlist_manager.py`
   - `m3u_parser.py` parses the M3U file
   - Channels are stored in `playlist.py` model
   - Displayed in `left_panel.py`

2. Channel Playback:
   - User selects channel from `left_panel.py`
   - `player_controller.py` handles playback
   - `playback_manager.py` manages video stream
   - EPG data displayed in `right_panel.py`

3. Settings Management:
   - Settings stored in SQLite database via `database.py`
   - `settings_controller.py` manages settings access
   - Settings affect UI through `themes.py` and `styles.py`

## Key Features

- M3U playlist support
- EPG integration
- Channel favorites
- Category filtering
- Search functionality
- Theme support
- Hardware acceleration
- Picture-in-picture mode
- Auto-reconnect
- Playlist auto-update

## Configuration

Application settings are stored in:
- `~/.simple_iptv/data/` - Application data
- `~/.simple_iptv/logs/` - Log files
- `~/.simple_iptv/cache/` - Cached data

## Dependencies

- PyQt6 - UI framework
- VLC - Video playback
- SQLite - Local storage
