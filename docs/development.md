# Development Guide

## Local Setup

Use a virtual environment from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Install native VLC separately. The Python package `python-vlc` is only a binding.

Tests use pytest, but `pytest` is not currently pinned in `requirements.txt`. Install it separately if your environment does not already provide it:

```bash
pip install pytest
```

The GitHub Actions lint workflow uses Python 3.12. If PyQt6 wheels are unavailable for a very new Python version on your platform, use Python 3.12 for local development.

## Run

```bash
python -m app.main
```

The app writes logs to `iptv_player.log` in the current working directory and stores local state in `~/.simple_iptv/database.db`.

## Environment

| Variable | Purpose |
|----------|---------|
| `IPTV_LOG_LEVEL` | Optional Python logging level. Defaults to `INFO`; invalid values fall back to `INFO`. |
| `QT_QPA_PLATFORM=offscreen` | Useful for headless Qt test runs. The pytest fixture sets it if missing. |
| `XDG_SESSION_TYPE`, `WAYLAND_DISPLAY`, `DISPLAY` | Read by VLC embedding code on Linux to detect Wayland/XWayland caveats. |

There is no `.env` file.

## Commands

Run from repo root.

| Task | Command | Notes |
|------|---------|-------|
| Install | `pip install -r requirements.txt` | Installs app, lint, and format dependencies. |
| Install pytest if missing | `pip install pytest` | Test runner is not pinned in `requirements.txt`. |
| Run app | `python -m app.main` | Requires native VLC for playback. |
| Tests | `python -m pytest -q` | Requires PyQt6 import support. |
| CI lint locally | `pylint --fail-under=9.5 $(git ls-files '*.py')` | Matches `.github/workflows/pylint.yml`. |
| Format | `black .` | Tool is installed, but no project config is checked in. |
| Sort imports | `isort .` | Tool is installed, but no project config is checked in. |
| Syntax check | `python -m compileall app core infra ui tests` | Useful when Qt runtime is unavailable. |

No packaging build command is configured. Do not document or automate release packaging until the repo has an explicit packaging configuration.

## Testing Workflow

Use focused pytest runs during development:

```bash
python -m pytest -q tests/test_imports.py
python -m pytest -q tests/test_models_and_services.py
python -m pytest -q
```

Current tests cover:

- import smoke checks
- model behavior
- settings persistence and legacy key sync
- playlist parsing/loading/validation
- EPG parsing/loading and timezone handling
- SQLite repositories
- Xtream client URL/auth/error behavior
- background controller stale-result handling
- selected PyQt widget and delegate behavior
- startup and VLC-unavailable dialog behavior

CI currently runs Pylint only on pull requests. Local test coverage is important because the workflow does not run pytest yet.

## Debugging Tips

### PyQt6 cannot be imported

Confirm the active virtual environment and install dependencies:

```bash
which python
python -m pip show PyQt6
pip install -r requirements.txt
```

If your Python version is too new for available PyQt6 wheels on your platform, use Python 3.12.

### VLC is unavailable

Install the native VLC app/runtime and restart the app. On Windows, confirm VLC is installed in one of the standard VideoLAN directories. On Linux, verify the current user session can access VLC libraries.

### Linux Wayland playback embedding fails

The VLC backend uses `set_xwindow` on Linux. Under Wayland, embedded playback may require XWayland. Check `XDG_SESSION_TYPE`, `WAYLAND_DISPLAY`, and `DISPLAY`, then try an X11/XWayland session if video does not appear.

### Playlist or EPG source fails

Check `iptv_player.log`. The app separates validation, network, parsing, and repository errors in service/controller paths. Use the playlist manager **Test Source** flow to validate a playlist without switching the active playlist.

### Reset local state

Stop the app and remove the SQLite database:

```bash
rm ~/.simple_iptv/database.db
```

The next app launch recreates the schema.

## Coding Expectations

- Keep UI code in `ui/`; do not make widgets talk directly to SQLite or VLC internals.
- Keep service/domain behavior in `core/`; avoid PyQt imports there unless there is already a clear boundary.
- Keep persistence changes in repositories and `SQLiteConnection`.
- Keep playlist identity source-aware.
- Keep channel list rendering virtualized through `QListView`, `QAbstractListModel`, and `QStyledItemDelegate`.
- Redact Xtream passwords in logs and UI summaries.
- Update docs when behavior, commands, setup, or roadmap status changes.
