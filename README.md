# Simple IPTV Player

Simple IPTV Player is a desktop application built using PyQt6 that allows users to load and play IPTV playlists and Electronic Program Guide (EPG) data. The application provides a user-friendly interface for managing channels, viewing program information, and customizing the viewing experience with themes.

## Features

- **Load and Play IPTV Playlists**: Supports M3U and M3U8 playlist formats.
- **EPG Support**: Load EPG data from XMLTV files or URLs to view current and upcoming program information.
- **Favorites Management**: Add and remove channels from favorites.
- **Search Functionality**: Search for channels within the current category.
- **Theme Customization**: Switch between light and dark themes.
- **Volume Control**: Adjust the playback volume.
- **Notifications**: Display notifications for various actions and events.

## Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/yourusername/simple-iptv-player.git
   cd simple-iptv-player
   ```

2. **Install dependencies**:
   Ensure you have Python 3.8+ and pip installed. Then, run:

   ```bash
   pip install -r requirements.txt
   ```

3. **Install VLC**:
   The application requires VLC to be installed on your system. Ensure VLC is installed and accessible in your system's PATH.

## Usage

1. **Run the application**:

   ```bash
   python simple_iptv/main.py
   ```

2. **Load a Playlist**:

   - Click on "Load Playlist" and select an M3U file to load channels.

3. **Load EPG Data**:

   - Load EPG data from a file or URL using the "Load EPG" button.

4. **Manage Favorites**:

   - Add channels to favorites by clicking the star button next to the channel name.

5. **Search Channels**:

   - Use the search bar to find channels within the current category.

6. **Change Theme**:
   - Switch between light and dark themes using the settings menu.

## Code Structure

- **Main Application**: `simple_iptv/main.py`
- **Views**: Located in `simple_iptv/views/`, including `main_window.py`, `player_widget.py`, and more.
- **Controllers**: Located in `simple_iptv/controllers/`, including `player_controller.py`.
- **Models**: Located in `simple_iptv/models/`, including `playlist.py` and `epg.py`.
- **Utilities**: Located in `simple_iptv/utils/`, including `database.py`, `m3u_parser.py`, and `epg_parser.py`.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request for any improvements or bug fixes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

- PyQt6 for the GUI framework.
- VLC for media playback capabilities.
