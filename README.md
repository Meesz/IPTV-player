# Simple IPTV Player

Simple IPTV Player is a PyQt desktop application for loading IPTV playlists, browsing channels, viewing XMLTV program data, and playing live streams through VLC. It keeps playlists, favorites, recent channels, and user preferences in a local SQLite database so the app state survives restarts.

## Highlights

- Load M3U and M3U8 playlists from a local file or an HTTP(S) URL.
- Load XMLTV EPG data from a local file or a remote URL.
- Browse channels by group, search within the current category or across the full playlist, and sort the visible list.
- Save favorite channels and keep a recent playback history.
- Show current program information directly in the channel list when EPG data is available.
- Play streams with VLC, including buffering status, automatic reconnect attempts, fullscreen toggle, and volume control.
- Persist playlist metadata and playback preferences between sessions.

## Requirements

- Python 3.10 or newer
- `pip`
- VLC media player installed on your system

The Python dependency `python-vlc` does not bundle the VLC application itself. The native VLC runtime must already be installed and available on your machine.

## Quick Start

```bash
git clone https://github.com/Meesz/IPTV-player.git
cd IPTV-player
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

On Windows PowerShell, activate the virtual environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## Install VLC

Install VLC before launching the app. Examples:

```bash
# Ubuntu / Debian
sudo apt install vlc

# Fedora
sudo dnf install vlc

# macOS (Homebrew)
brew install --cask vlc
```

On Windows, install VLC from the official VideoLAN distribution and then start the application again.

## Running the App

Run the application from the repository root:

```bash
python -m app.main
```

On first launch the app will:

- create a SQLite database at `~/.simple_iptv/database.db`
- create the parent directory automatically if it does not exist
- write application logs to `iptv_player.log` in the current working directory

## Usage

### 1. Add and load a playlist

Open **File -> Playlist Manager** or press `Ctrl+P`.

- Use **Add Playlist -> From File** for local `.m3u` or `.m3u8` files.
- Use **Add Playlist -> From URL** for remote HTTP(S) playlists.
- Select a saved playlist to load its channels into the main view.

### 2. Load EPG data

You can load EPG data in two ways:

- **EPG -> Load from File** for local XMLTV files
- enter an EPG URL in the top toolbar and click **Load**

Use `Ctrl+R` to refresh the last EPG source.

### 3. Browse and search channels

- Filter channels by category from the left panel.
- Use the search bar to narrow the list.
- Toggle whether search stays inside the current category.
- Sort the visible channels by name, group, or favorites-first ordering.

### 4. Start playback

- Double-click a channel to start playback.
- If you prefer single-click playback, enable **View -> Play on Single Click**.
- Use the player controls to play, stop, and change volume.
- Double-click the video area to toggle fullscreen while a stream is playing.

### 5. Save favorites and history

- Use the star button in the right panel to add or remove the current channel from favorites.
- The app automatically stores recent channels with their playlist source.
- Favorites and recent history remain available after restart.

### 6. Show current program details

When EPG data is loaded, the app can display the current program next to channels in the list. Toggle this with **View -> Show Current Program in Lists**.

## Supported Inputs

- Playlist files: `.m3u`, `.m3u8`
- Playlist URLs: `http://`, `https://`
- EPG sources: XMLTV files and XMLTV URLs

## Project Layout

- `app/`: application startup and dependency wiring
- `core/`: domain models and business services
- `infra/`: SQLite repositories, playlist and EPG parsers, VLC backend
- `ui/`: Qt windows, widgets, dialogs, styles, and controllers
- `tests/`: smoke and service-level tests

For the architecture walkthrough and refactoring notes, see [walkthrough.md](walkthrough.md).

## Troubleshooting

### VLC backend unavailable

If the player area shows a VLC initialization error:

- make sure the VLC desktop application is installed, not just the Python package
- restart the app after installing VLC
- verify that VLC is available to the current user session

### Playlist URL fails to load

- make sure the URL starts with `http://` or `https://`
- confirm the playlist is reachable from your network
- verify that the remote source returns valid M3U content

### Playlist or EPG parsing fails

- confirm the file format is valid M3U, M3U8, or XMLTV
- check `iptv_player.log` for the underlying error
- reload the source after fixing malformed metadata

### Reset local app data

If you want to clear saved playlists, favorites, history, and settings, remove the database file:

```bash
rm ~/.simple_iptv/database.db
```

The database will be recreated automatically on the next launch.

## Contributing

Contributions are welcome. Keep changes aligned with the current layered structure in `app`, `core`, `infra`, and `ui`.

## License

This repository does not currently include a `LICENSE` file.
