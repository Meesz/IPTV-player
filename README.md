# Simple IPTV Player

Simple IPTV Player is a local PyQt6 desktop app for loading IPTV sources, browsing channels, viewing XMLTV program data, and playing live streams through VLC. It stores playlists, favorites, recent channels, EPG cache data, and UI preferences in a local SQLite database.

This repo is a desktop application, not a web service. There is no backend server, cloud sync, account system, or packaged release workflow configured in the current codebase.

## Current Features

- Load M3U/M3U8 playlists from local files or HTTP(S) URLs.
- Add Xtream-compatible live TV sources through `player_api.php` credentials.
- Test playlist sources from the playlist manager without replacing the active playlist.
- Load XMLTV EPG data from local XML/XML.GZ files or HTTP(S) URLs. Xtream sources load the provider's own guide (`xmltv.php`) automatically when no manual guide is set.
- Browse channels by category, search by name/group, sort results, and show current program metadata when EPG data is available.
- Render large channel lists through a `QListView` model/delegate instead of one widget per row.
- Show channel logos from HTTP(S) URLs or local image paths, with a generated placeholder while loading or on failure.
- Play streams through native VLC with buffering status, retry handling, reconnect caps, mute, fullscreen, copy URL, and manual retry controls.
- Save favorites and recent channels with source-aware channel identity.
- Persist UI state such as theme, window size, splitter sizes, active tab, selected category, search text, sort mode, mute state, and list display preferences.
- Log application activity to `~/.simple_iptv/iptv_player.log`.

## Tech Stack

- Python desktop application
- PyQt6 for the UI
- SQLite through the standard `sqlite3` module
- VLC playback through `python-vlc` plus the native VLC runtime
- `requests` for playlist, EPG, and Xtream HTTP calls; Qt's `QNetworkAccessManager` for channel logo images
- pytest and pytest-qt for tests, pinned in `requirements-dev.txt`
- Ruff for linting and formatting (configured in `pyproject.toml`) and mypy for type checking
- GitHub Actions CI on pull requests and pushes to `main`: ruff, pytest, and a blocking mypy error-count ratchet

## Requirements

- Python 3.12 or newer. CI tests run on Python 3.12 and 3.14, and Ruff/mypy target 3.12. No `requires-python` is declared, so older versions are simply untested.
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
pip install -r requirements.txt       # to run the app
pip install -r requirements-dev.txt   # for development: runtime deps plus pytest, ruff, mypy, pre-commit
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
- Log file in the app data directory: `~/.simple_iptv/iptv_player.log` (rotates at 5 MB, keeping `.1` and `.2` backups)

To reset local app state, stop the app and remove the database:

```bash
rm ~/.simple_iptv/database.db
```

The database is recreated on the next launch.

### Back up before upgrading

Schema migrations run automatically at startup and are one-way: once a newer version has
migrated `database.db`, an older checkout cannot reliably read it. Before pulling a new
version, stop the app and copy the database together with its WAL files:

```bash
mkdir -p ~/simple_iptv_backup
cp ~/.simple_iptv/database.db* ~/simple_iptv_backup/
```

To roll back, stop the app, check out the older version, and copy the files back into
`~/.simple_iptv/`. The backup contains your Xtream credentials (see Current Limitations), so
keep it private.

## Environment Variables

| Name | Used by | Default | Purpose |
|------|---------|---------|---------|
| `IPTV_LOG_LEVEL` | `app/main.py` | `INFO` | Sets Python logging level. Invalid values fall back to `INFO`. |
| `QT_QPA_PLATFORM` | Qt/tests | unset | Set to `offscreen` for headless test runs when needed. The pytest fixture sets this if it is missing. On Linux Wayland with XWayland the app sets `xcb;wayland` itself when this is unset; an existing value is never overridden. |
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
| Lint | `ruff check .` |
| Check formatting | `ruff format --check .` |
| Format Python files | `ruff format .` |
| Type check (CI blocks if the error count rises) | `mypy app core infra ui` |
| Install git hooks | `pre-commit install` |
| Syntax/import sanity check | `python -m compileall app core infra ui tests` |

No packaged build command is configured. `MANIFEST.in` exists, but `pyproject.toml` has no `[project]` or `[build-system]` table, so the repo cannot be built as a package. Packaging/release distribution is not defined.

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

- Playback depends on native VLC and platform-specific embedding. On Linux Wayland sessions the app requests the `xcb` (XWayland) Qt platform automatically unless `QT_QPA_PLATFORM` is set; playback is refused with an error when embedded video is impossible (for example no XWayland).
- Xtream passwords are stored in the local SQLite database so sources can be reloaded. The database itself is not encrypted. On POSIX systems the default data directory `~/.simple_iptv` is restricted to mode 0700 and `database.db` to 0600 (Windows permissions are not changed). Log handlers mask `password`-style query values and URL userinfo passwords, but Xtream stream URLs carry the password in the path, so channel URLs must not be logged.
- Remote downloads are bounded: very large playlists, Xtream responses, or EPG files (including oversized decompressed gzip EPGs) are rejected with an error, and downloads that exceed a time budget are aborted on a best-effort basis.
- There is no account system, remote sync, or multi-device state.
- Channel logos are fetched directly by the channel list (10 s transfer timeout, up to 500 images cached in memory, nothing cached on disk). Unlike playlist/EPG downloads, logo responses have no size limit.
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
- [Coding agent guide](AGENTS.md)

Historical, point-in-time reports (not current guidance): [Phase 3 status](docs/phase3.md),
[refactoring walkthrough](walkthrough.md), [production readiness review](PRODUCTION_READINESS.md),
[test audit](TEST_AUDIT.md), and [UI audit](UI_AUDIT.md).

## License

This repository does not currently include a `LICENSE` file.
