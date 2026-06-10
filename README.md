# Simple IPTV Player

Simple IPTV Player is a local PyQt6 desktop app for loading IPTV sources, browsing channels, viewing XMLTV program data, and playing live streams through VLC. It stores playlists, favorites, recent channels, EPG cache data, and UI preferences in a local SQLite database.

This repo is a desktop application, not a web service. There is no backend server, cloud sync, account system, or packaged release workflow configured in the current codebase.

## Current Features

- Load M3U/M3U8 playlists from local files or HTTP(S) URLs.
- Add Xtream-compatible live TV sources through `player_api.php` credentials.
- Test playlist sources from the playlist manager without replacing the active playlist.
- Load XMLTV EPG data from local XML/XML.GZ files or HTTP(S) URLs.
- Browse channels by category, search by name/group, sort results, and show current program metadata when EPG data is available.
- Render large channel lists through a `QListView` model/delegate instead of one widget per row.
- Play streams through native VLC with buffering status, retry handling, reconnect caps, mute, fullscreen, copy URL, and manual retry controls.
- Save favorites and recent channels with source-aware channel identity.
- Persist UI state such as theme, window size, splitter sizes, active tab, selected category, search text, sort mode, mute state, and list display preferences.
- Log application activity to `iptv_player.log`.

## Tech Stack

- Python desktop application
- PyQt6 for the UI
- SQLite through the standard `sqlite3` module
- VLC playback through `python-vlc` plus the native VLC runtime
- `requests` for playlist, EPG, and Xtream HTTP calls
- pytest for tests, pinned in `requirements-dev.txt`
- Pylint and pytest in GitHub Actions CI
- Black and isort for formatting, configured in `pyproject.toml`

## Requirements

- Python 3.10 or newer. The current GitHub Actions workflow uses Python 3.12.
- `pip`
- Native VLC media player installed on the machine

`python-vlc` does not bundle VLC itself. Install the VLC desktop/runtime package separately before expecting playback to work.

Install VLC examples:

```bash
# Ubuntu / Debian
sudo apt install vlc

# Fedora
sudo dnf install vlc

# macOS with Homebrew
brew install --cask vlc
```

On Windows, install VLC from VideoLAN. The app looks in the standard `C:\Program Files\VideoLAN\VLC` or `C:\Program Files (x86)\VideoLAN\VLC` paths depending on Python architecture.

## Installation

Run from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt       # runtime deps only
pip install -r requirements-dev.txt   # adds pytest, black, isort, pylint
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Run The App

```bash
python -m app.main
```

On first launch the app creates:

- SQLite database: `~/.simple_iptv/database.db`
- Log file in the current working directory: `iptv_player.log`

To reset local app state, stop the app and remove the database:

```bash
rm ~/.simple_iptv/database.db
```

The database is recreated on the next launch.

## Environment Variables

| Name | Used by | Default | Purpose |
|------|---------|---------|---------|
| `IPTV_LOG_LEVEL` | `app/main.py` | `INFO` | Sets Python logging level. Invalid values fall back to `INFO`. |
| `QT_QPA_PLATFORM` | Qt/tests | unset | Set to `offscreen` for headless test runs when needed. The pytest fixture sets this if it is missing. |
| `XDG_SESSION_TYPE`, `WAYLAND_DISPLAY`, `DISPLAY` | VLC embedding on Linux | system-provided | Used to detect Wayland/XWayland embedding caveats. |

See `.env.example` for a template. None of these variables are required for normal use.

## Common Commands

Run commands from the repository root unless noted.

| Task | Command |
|------|---------|
| Install runtime deps | `pip install -r requirements.txt` |
| Install dev/test deps | `pip install -r requirements-dev.txt` |
| Run app | `python -m app.main` |
| Run tests | `python -m pytest -q` |
| Check formatting | `black --check . && isort --check .` |
| Format Python files | `black . && isort .` |
| Run CI lint locally | `pylint --fail-under=9.5 $(git ls-files '*.py')` |
| Syntax/import sanity check | `python -m compileall app core infra ui tests` |

No packaged build command is configured. Packaging/release distribution is not defined.

## Project Structure

- `app/` - application startup, logging, dependency wiring, and top-level error dialogs.
- `core/` - domain models, typed settings, service logic, and domain error types.
- `infra/db/` - SQLite connection management and repositories.
- `infra/parsers/` - M3U/M3U8 and XMLTV parsing.
- `infra/providers/` - Xtream-compatible API client.
- `infra/playback/` - VLC initialization and platform-specific video embedding.
- `ui/controllers/` - Qt signal-based controllers and background task orchestration.
- `ui/windows/` - main application window.
- `ui/widgets/` - player, panels, channel list view, notifications, loading overlay, and EPG widgets.
- `ui/dialogs/` - playlist manager and Xtream source dialogs.
- `ui/styles/` - theme tokens and Qt stylesheets.
- `tests/` - pytest coverage for models, services, repositories, parsers, controllers, and selected UI behavior.
- `docs/` - product, architecture, development, and roadmap notes.

## Current Limitations

- Playback depends on native VLC and platform-specific embedding. Linux Wayland sessions may require XWayland for embedded video.
- Xtream passwords are stored in the local SQLite database so sources can be reloaded. Logs are expected to redact passwords, but the database itself is not encrypted.
- There is no account system, remote sync, or multi-device state.
- Playlist and EPG downloads use blocking HTTP calls inside worker tasks; cancellation ignores stale results but cannot always abort an in-flight network request immediately.
- Packaging/release distribution is not defined.

## Roadmap Summary

Near-term work should focus on dependency/tooling cleanup, stronger integration test coverage, clearer packaging decisions, and continued polish around source validation, error reporting, and playback edge cases. Longer-term ideas such as cloud sync, recording, and advanced provider features are speculative.

See [docs/roadmap.md](docs/roadmap.md) for the detailed roadmap.

## Deeper Docs

- [Product notes](docs/product.md)
- [Architecture](docs/architecture.md)
- [Development guide](docs/development.md)
- [Roadmap](docs/roadmap.md)
- [Phase 3 status](docs/phase3.md)
- [Refactoring walkthrough](walkthrough.md)
- [Coding agent guide](AGENTS.md)

## License

This repository does not currently include a `LICENSE` file.
