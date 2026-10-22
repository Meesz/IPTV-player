# Simple IPTV Player

[![Tests](https://github.com/Meesz/IPTV-player/actions/workflows/tests.yml/badge.svg)](https://github.com/Meesz/IPTV-player/actions/workflows/tests.yml)
[![Lint](https://github.com/Meesz/IPTV-player/actions/workflows/lint.yml/badge.svg)](https://github.com/Meesz/IPTV-player/actions/workflows/lint.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

A local desktop app for watching live TV from your own IPTV sources. Load M3U playlists or Xtream Codes accounts, browse channels with an XMLTV program guide, and play streams through VLC.

It is a local PyQt6 app, not a web service: there is no backend, account system, cloud sync, recording, or packaged release. Everything is stored in a local SQLite database.

## Features

- Load M3U/M3U8 playlists from local files or HTTP(S) URLs, or add Xtream Codes live TV sources.
- Test a source without replacing the active playlist.
- Load XMLTV guide data from files (XML/XML.GZ) or URLs; Xtream sources use the provider's guide automatically.
- Browse by category (with a searchable category picker for providers with hundreds of categories), search, sort, and see the current program per channel.
- Handles large channel lists smoothly, with channel logos and a placeholder while loading.
- Playback with buffering status, automatic reconnect, retry, mute, fullscreen, and copy-URL controls.
- Favorites and recently played channels.
- Remembers your window layout, active tab, category, search text, sort mode, and mute state.

## Quick start

Requirements:

- Python 3.12 or newer.
- Native VLC media player. `python-vlc` does not bundle VLC, so install it separately or playback will not work.

```bash
# Ubuntu / Debian
sudo apt install vlc
# Fedora
sudo dnf install vlc
# macOS with Homebrew
brew install --cask vlc
```

On Windows, install VLC from VideoLAN. The app looks in `C:\Program Files\VideoLAN\VLC` or `C:\Program Files (x86)\VideoLAN\VLC`, depending on Python architecture.

Then, from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.main
```

## Using the app

**Add a source.** Click **Sources** in the header (or press `Ctrl+P`, or use File > Playlist Manager). In the Playlist Manager, open the **Add** menu and choose **From File...** (`.m3u`, `.m3u8`), **From URL...**, or **From Xtream Codes...**. The Xtream dialog asks for server URL, username, password, and output format; when editing a saved source, leaving the password blank keeps the saved one. The manager also offers **Edit** (rename, then change the file, URL, or Xtream details; the location of the currently active source cannot be changed), Remove, **Test Source**, and **Load Playlist**; right-clicking a source offers Edit, Test Source, and Remove.

**Add a program guide (EPG).** Paste an XMLTV URL into the header's "XMLTV guide URL" field and click **Load guide**, or use EPG > **Load from File...**. EPG > **Refresh Last Source** (`Ctrl+R`) reloads the last guide. Parsed guide data is cached in the database, so it is still shown after a restart; manual file/URL guides are only re-downloaded when you load or refresh them. For an Xtream source with no manual guide, the provider's guide loads automatically after the playlist loads, and is downloaded again on a later playlist load once the cached copy is older than 12 hours; leaving the URL field empty and clicking **Load guide** switches back to it. A status chip shows when the guide was last updated.

**Browse.** The library has **Channels**, **Favorites**, and **Recent** tabs (Recent holds the last 12 channels). Pick a category from the searchable **Category** picker (or "All"), type in "Search channels or groups" (`Ctrl+L` focuses it), and sort A-Z, Z-A, by Group, or Favorites First. "Search within category" is on by default; turn it off to search all channels.

**Play.** Double-click a channel, or enable View > **Play on Single Click**. The player has play, stop, mute, volume, fullscreen, **Retry stream**, **Copy stream URL**, and **Channel info** buttons. Mark a favorite with the star **Favorite** button in the channel details panel. The View menu also toggles "Show Current Program in Lists" and "Show Library Panel".

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+P` | Open Playlist Manager |
| `Ctrl+R` | Refresh last EPG source |
| `Ctrl+L` | Focus channel search |
| `Ctrl+Q` | Quit |
| `Space` | Play (or restart) the selected channel; there is no pause |
| `M` | Mute |
| `F` | Fullscreen |
| `Esc` | Exit fullscreen |
| `Up` / `Down` / `PgUp` / `PgDn`, `Enter`, `Esc` | Navigate, confirm, and close the category and sort pickers |

`Space`, `M`, and `F` are handled by the main window, so they only work when the focused widget does not consume the key. Text fields (channel search, category search, XMLTV URL) and the channel lists (which use Qt's default key handling, such as type-ahead search) can swallow them.

## Your data

On first launch the app creates, in `~/.simple_iptv/`:

- `database.db`: playlists, favorites, recent channels, EPG cache, and UI state.
- `iptv_player.log`: rotates at 5 MB, keeping `.1` and `.2` backups.

To reset local state, stop the app and run `rm ~/.simple_iptv/database.db`; it is recreated on the next launch.

**Back up before upgrading.** Schema migrations run automatically at startup and are one-way: once a newer version has migrated `database.db`, an older checkout cannot reliably read it. Before pulling a new version, stop the app and copy the database together with its WAL files:

```bash
mkdir -p ~/simple_iptv_backup
cp ~/.simple_iptv/database.db* ~/simple_iptv_backup/
```

To roll back, stop the app, check out the older version, and copy the files back into `~/.simple_iptv/`. The backup contains your Xtream credentials (see [Limitations](#limitations)), so keep it private.

### Environment variables

None are required for normal use; see `.env.example` for a template.

| Name | Default | Purpose |
|------|---------|---------|
| `IPTV_LOG_LEVEL` | `INFO` | Python logging level. Invalid values fall back to `INFO`. |
| `QT_QPA_PLATFORM` | unset | Qt platform plugin. Set to `offscreen` for headless runs (the pytest fixture does this if unset). An existing value is never overridden. |
| `WAYLAND_DISPLAY`, `XDG_SESSION_TYPE`, `DISPLAY` | system-provided | On Linux, if a Wayland session is detected (`WAYLAND_DISPLAY` set or `XDG_SESSION_TYPE=wayland`), `DISPLAY` is set (XWayland available), and `QT_QPA_PLATFORM` is unset, the app sets `QT_QPA_PLATFORM=xcb;wayland` itself. |

## Limitations

- Playback depends on native VLC and platform-specific video embedding. Playback is refused with an error when embedded video is impossible (for example, a Wayland session without XWayland).
- Xtream passwords are stored in the local SQLite database so sources can be reloaded, and the database is not encrypted. On POSIX systems `~/.simple_iptv` is restricted to mode 0700 and `database.db` to 0600 (Windows permissions are not changed). Logs mask `password`-style query values and URL userinfo passwords, but Xtream stream URLs carry the password in the path, so channel URLs must not be logged.
- Remote downloads are bounded: very large playlists, Xtream responses, or EPG files (including oversized decompressed gzip EPGs) are rejected with an error, and downloads exceeding a time budget are aborted on a best-effort basis.
- No account system, remote sync, or multi-device state.
- Channel logos are fetched directly by the channel list (10 s transfer timeout, up to 500 images cached in memory, nothing cached on disk). Unlike playlist and EPG downloads, logo responses have no size limit.
- Playlist and EPG downloads use blocking HTTP calls in worker tasks; cancelling ignores stale results but cannot always abort an in-flight request immediately.
- Packaging and release distribution are not defined.

## Development

```bash
pip install -r requirements-dev.txt   # runtime deps plus pytest, ruff, mypy, pre-commit
```

Run from the repository root:

| Task | Command |
|------|---------|
| Tests | `python -m pytest -q` |
| Lint | `ruff check .` |
| Check formatting | `ruff format --check .` |
| Format | `ruff format .` |
| Type check (CI blocks if the error count rises) | `mypy app core infra ui` |
| Install git hooks | `pre-commit install` |

CI runs on pull requests and pushes to `main`: ruff check, ruff format check, pytest (Python 3.12 and 3.14), and the mypy error-count ratchet.

No packaged build is configured: `MANIFEST.in` exists, but `pyproject.toml` has no `[project]` or `[build-system]` table.

| Path | Contents |
|------|----------|
| `app/` | Startup, logging, dependency wiring, top-level error dialogs |
| `core/` | Domain models, typed settings, services, domain errors |
| `infra/` | SQLite (`db/`), M3U/XMLTV parsers, Xtream client (`providers/`), VLC setup (`playback/`) |
| `ui/` | Controllers, main window, widgets, dialogs, styles |
| `tests/` | pytest suite for models, services, repositories, parsers, controllers, selected UI |
| `docs/` | Product, architecture, development, and roadmap notes |

See [docs/development.md](docs/development.md) for the full workflow and [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute.

## Roadmap

Near-term work focuses on dependency/tooling cleanup, stronger integration tests, clearer packaging decisions, and polish around source validation, error reporting, and playback edge cases. Cloud sync, recording, and advanced provider features are speculative. See [docs/roadmap.md](docs/roadmap.md).

## Docs

- [Product notes](docs/product.md)
- [Architecture](docs/architecture.md)
- [Development guide](docs/development.md)
- [Roadmap](docs/roadmap.md)
- [Coding agent guide](AGENTS.md)

Historical, point-in-time reports (not current guidance): [Phase 3 status](docs/archive/phase3.md),
[refactoring walkthrough](docs/archive/walkthrough.md), [production readiness review](docs/archive/PRODUCTION_READINESS.md),
test audits ([first](docs/archive/TEST_AUDIT.md), [2026-10-20](docs/archive/TEST_AUDIT_2026-10-20.md)), [UI audit](docs/archive/UI_AUDIT.md), and [performance audit](docs/archive/PERFORMANCE_AUDIT.md).

## License

Released under the [MIT License](LICENSE).
