# Development Guide

## Local Setup

Use a virtual environment from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # includes runtime + pytest, ruff, mypy, pre-commit
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Install native VLC separately. The Python package `python-vlc` is only a binding.

Use Python 3.12 or newer. The GitHub Actions lint workflow uses Python 3.12; the tests workflow runs on Python 3.12 and 3.14. No `requires-python` is declared, so older versions are untested. If PyQt6 wheels are unavailable for a very new Python version on your platform, use Python 3.12 for local development.

## Run

```bash
python -m app.main
```

The app writes logs to `~/.simple_iptv/iptv_player.log` and stores local state in `~/.simple_iptv/database.db`. If the log file cannot be opened, the app falls back to console-only logging.
The log rotates at 5 MB (two backups) and each run is bracketed by `=== Session start/end ===` lines. Besides service
activity it records channels played (by name, never URL), playback state transitions, reconnects, every notification
shown to the user, handled controller failures with tracebacks, and Qt runtime warnings (logger `qt`).

## Environment

| Variable | Purpose |
|----------|---------|
| `IPTV_LOG_LEVEL` | Optional Python logging level. Defaults to `INFO`; invalid values fall back to `INFO`. |
| `QT_QPA_PLATFORM=offscreen` | Useful for headless Qt test runs. The pytest fixture sets it if missing. On Linux Wayland the app sets `xcb;wayland` itself when this is unset; an existing value is never overridden. |
| `XDG_SESSION_TYPE`, `WAYLAND_DISPLAY`, `DISPLAY` | Read by VLC embedding code on Linux to detect Wayland/XWayland caveats. |

See `.env.example` for available variables. The app does not require a `.env` file — these variables are optional overrides.

## Commands

Run from repo root.

| Task | Command | Notes |
|------|---------|-------|
| Install dev deps | `pip install -r requirements-dev.txt` | Includes runtime + pytest, ruff, mypy, pre-commit. |
| Run app | `python -m app.main` | Requires native VLC for playback. |
| Tests | `python -m pytest -q` | Requires PyQt6 import support. |
| Lint | `ruff check .` | Matches `.github/workflows/lint.yml`. |
| Format | `ruff format .` | Config lives in `pyproject.toml` (line-length 120, target py312). |
| Check formatting | `ruff format --check .` | Useful in CI or before committing. |
| Type check | `mypy app core infra ui` | Blocking error-count ratchet in CI: fails if the error count exceeds the maximum recorded in `.github/workflows/lint.yml` (`MYPY_MAX_ERRORS`). |
| Install git hooks | `pre-commit install` | Runs ruff (lint + format) and hygiene hooks on commit. |
| Syntax check | `python -m compileall app core infra ui tests` | Useful when Qt runtime is unavailable. |

No packaging build command is configured. Do not document or automate release packaging until the repo has an explicit packaging configuration.

## Testing Workflow

Use focused pytest runs during development:

```bash
python -m pytest -q tests/test_credential_redaction.py
python -m pytest -q tests/test_models_and_services.py
python -m pytest -q
```

Qt tests share the session `qapp` fixture in `tests/conftest.py` and need `QT_QPA_PLATFORM=offscreen` on headless machines. An autouse `isolated_home` fixture points `Path.home()` at a temp directory so no test can reach the real `~/.simple_iptv/`. Another autouse fixture closes and deletes top-level widgets after each test, so set stylesheets on the widget under test rather than on `qapp`. Use `tests/_http.py` (`FakeResponse`, `json_response`) instead of defining another fake `requests` response.

Current tests cover:

- model behavior
- settings persistence and legacy key sync, verified by reloading from SQLite
- restart restore of the active playlist (file, URL, Xtream) across fresh service instances (`tests/test_restart_restore.py`)
- playlist parsing/loading/validation, URL download retries, and channel sort order (`tests/test_m3u_parser.py`, `tests/test_playlist_url_and_query.py`)
- Xtream input validation and authentication decisions (`tests/test_xtream_validation.py`)
- credential redaction in logs and error messages for Xtream, EPG URL, and M3U URL sources
- EPG parsing/loading, timezone handling, and now/next boundaries (`tests/test_epg_now_next.py`, `tests/test_epg_and_settings_robustness.py`)
- the optimized XMLTV date parsing and Xtream channel-mapping paths (`tests/test_backend_performance_paths.py`)
- SQLite repositories and schema migrations (playlists and legacy favorites; `tests/test_sqlite_migration.py`, `tests/test_favorites_migration.py`)
- Xtream client URL/auth/error behavior
- background controller stale, failure, and cancellation handling (`tests/test_async_controllers.py`), plus cancellation of the playlist-manager probe (`tests/test_probe_cancellation.py`)
- service-level playlist switching (`tests/test_playlist_switching.py`)
- download size/time budgets (`tests/test_download_limits.py`)
- playback history pruning (`tests/test_history_repository.py`)
- log setup and fallbacks, redaction, and keeping stream URLs out of logs (`tests/test_logging.py`)
- channel logo loading and caching (`tests/test_logo_provider.py`)
- player fullscreen round-trips, video surface switching, and platform embedding decisions (`tests/test_player_fullscreen.py`, `tests/test_player_surface.py`, `tests/test_video_embedding.py`)
- the widget-to-repository/parser/HTTP import boundary (`tests/test_layer_boundaries.py`)
- headless `MainWindow` wiring with VLC disabled: load, play, favorites, history, save on close, restart (`tests/test_main_window_wiring.py`)
- selected PyQt widget and delegate behavior (`tests/test_searchable_combo_box.py`, `tests/test_channel_list_view_updates.py`)
- theme tokens (painter-safe colors), channel row painting, and main-window/dialog layout invariants such as no clipping or overlap, elision, and empty-state actions (`tests/test_ui_theme.py`, `tests/test_ui_layout.py`)
- startup and VLC-unavailable dialog behavior

CI runs lint and tests on pull requests and on pushes to `main` (`.github/workflows/lint.yml` and `.github/workflows/tests.yml`). The lint workflow runs `ruff check`, `ruff format --check`, and `mypy`; the mypy step is a blocking error-count ratchet that fails when the count exceeds `MYPY_MAX_ERRORS` (lower it as errors are fixed, never raise it).

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

The VLC backend uses `set_xwindow` on Linux, which needs the `xcb` Qt platform. On Wayland the app requests `xcb;wayland` automatically when `DISPLAY` (XWayland) is set and `QT_QPA_PLATFORM` is unset. If playback is refused with "Embedded video needs X11", check the `Qt platform:` line in the log, `XDG_SESSION_TYPE`, `WAYLAND_DISPLAY`, `DISPLAY`, and any `QT_QPA_PLATFORM` override (use `xcb`).

### Playlist or EPG source fails

Check `~/.simple_iptv/iptv_player.log`. The app separates validation, network, parsing, and repository errors in service/controller paths. Use the playlist manager **Test Source** flow to validate a playlist without switching the active playlist.

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
