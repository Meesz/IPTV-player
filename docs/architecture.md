# Architecture

## Overview

Simple IPTV Player is a layered PyQt6 desktop app. The app starts in `app/main.py`, wires repositories, services, controllers, and the main Qt window, then keeps runtime state inside Qt controllers, domain services, and a local SQLite database.

There is no frontend/backend split. Everything runs in one desktop process.

## Layer Responsibilities

| Layer | Paths | Responsibility |
|-------|-------|----------------|
| Startup | `app/main.py` | Configure logging, create `QApplication`, install the exception hook, wire dependencies, show startup/VLC dialogs, open `MainWindow`. |
| Domain | `core/models.py`, `core/errors.py`, `core/services/` | Typed models, channel/source identity, settings shape, service-level validation, source loading, EPG lookup, favorites/history/settings behavior. |
| Infrastructure | `infra/db/`, `infra/parsers/`, `infra/providers/`, `infra/playback/` | SQLite persistence, M3U/XMLTV parsing, Xtream HTTP calls, VLC runtime setup and platform video embedding. |
| UI controllers | `ui/controllers/` | Qt signals, background playlist/EPG workers, stale-result suppression, controller-to-service orchestration. |
| UI widgets/windows | `ui/windows/`, `ui/widgets/`, `ui/dialogs/`, `ui/styles/` | Main window, panels, player widget, playlist dialogs, channel list model/delegate, notifications, themes, and user interaction. |

## Runtime Data Flow

1. `app/main.py` creates `SQLiteConnection`, repositories, services, controllers, and `MainWindow`.
2. `MainWindow` connects Qt signals from menus, panels, controllers, dialogs, and player controls.
3. Playlist and EPG loads are started through `PlaylistController` and `EPGController`.
4. Controllers create `BackgroundTask` instances on `QThreadPool` and call service methods with progress and cancellation callbacks.
5. Services validate inputs, call parsers/providers/repositories, and return domain models.
6. Controllers emit success/error/progress signals back to `MainWindow`.
7. `MainWindow` updates the left panel, right panel, status chips, loading overlay, favorites, history, and persisted settings.

## Playlist Sources

The current source types are:

- `PlaylistSourceType.FILE` - local M3U/M3U8 file.
- `PlaylistSourceType.URL` - HTTP(S) M3U/M3U8 URL.
- `PlaylistSourceType.XTREAM` - Xtream-compatible source using server URL, username, password, and output format.

`PlaylistReference.source_identity` is the stable stored identity for a playlist source. File sources normalize to absolute paths, URL sources use the trimmed URL, and Xtream sources use normalized server URL plus username/output. Channel identity is source-aware through `Channel.identity_key()`, which returns `(url, playlist_path)`.

## EPG Flow

EPG sources are XMLTV files or URLs. URL loads download to a temporary XML/XML.GZ file, then reuse the file parser. Parsed programs are stored in SQLite and kept in memory for the active session.

Program times are normalized to timezone-aware UTC datetimes. UI display converts times to the local timezone when rendering channel rows.

- Programmes that share a channel and start time (whole-second UTC) resolve "last wins": `EPGParser` replaces the earlier entry and adds a `duplicate_programme` parse warning, and `EPGRepository` saves with `INSERT OR REPLACE`.
- Malformed XML (and other `ValueError` parse failures) from `EPGParser` is converted by `EPGService` into a `ParsingError`. The underlying parser error (logged and chained as the cause) includes the line and column; the `ParsingError` shown to the user names only the file.
- URL downloads are size- and time-bounded (see Download Limits). Gzip EPGs are decompressed through `_LimitedReader` in `infra/parsers/epg_parser.py`, which fails once decompressed data exceeds `MAX_EPG_DECOMPRESSED_BYTES`.

## Download Limits

Remote playlist, Xtream, and EPG downloads stream through `read_bounded` in `core/bounded_download.py`, using the constants in `core/limits.py` (`MAX_PLAYLIST_DOWNLOAD_BYTES`, `MAX_EPG_DOWNLOAD_BYTES`, `MAX_XTREAM_RESPONSE_BYTES`, and per-source `*_DOWNLOAD_DEADLINE_SECONDS`). Exceeding a download budget raises `DownloadLimitError` (a `NetworkError` subclass) without the URL in the message, and `PlaylistService` does not retry it. The separate `MAX_EPG_DECOMPRESSED_BYTES` gzip limit is enforced by `_LimitedReader` and surfaces as a `ParsingError`.

- The byte budgets (declared `Content-Length` and bytes actually read) are the hard memory guard.
- The wall-clock deadline is best-effort: it is checked between chunks, so a server that trickles data can overrun it. Each socket read is still bounded by the request timeout.

## Persistence Model

The default database path is:

```text
~/.simple_iptv/database.db
```

`SQLiteConnection` initializes and migrates tables at startup. Startup fails fast if database initialization fails. Each legacy-table migration (playlists, favorites) runs in one explicit transaction, so a failure rolls back to the legacy shape and the migration is retried on the next start. Every connection applies the same per-connection PRAGMAs (`synchronous`, `cache_size`, `temp_store`) and an explicit busy timeout; `journal_mode=WAL` is set once at initialization.

Main tables:

- `settings` - string key/value settings, including legacy compatibility keys.
- `playlists` - saved playlist references, source identity, Xtream credentials, channel count, last status, and last error.
- `favorites` - source-aware favorites keyed by URL and playlist path.
- `recent_channels` - recent playback history keyed by URL and playlist path, pruned to the newest 200 entries on each write.
- `epg_data` - cached EPG programs by channel ID and start time.

SQLite uses WAL mode, `synchronous=NORMAL`, a small cache, and memory temp store.

## State Management

- Persistent app settings are represented by `core.models.Settings` and handled by `SettingsService`.
- The active playlist lives in `PlaylistService.current_playlist`.
- Current UI selections and controls live in `MainWindow` and child widgets, with selected values written back through `SettingsController`.
- Favorites and history are persisted immediately through their repositories.
- Playlist/EPG background task state is owned by the corresponding controller. Stale task results are ignored when a newer load starts.

There is no global state management library.

## Playback Boundary

`infra/playback/vlc_backend.py` initializes the native VLC runtime and creates media players. `ui/widgets/player_widget.py` owns the playback UI state, reconnect timer, media event handler, and platform-specific video output binding.

Platform embedding behavior:

- Windows: `set_hwnd`
- Linux: `set_xwindow`
- macOS: `set_nsobject`

Linux Wayland sessions may need XWayland for embedded video. The backend reports a warning when it detects a risky Wayland setup.

Shutdown: `MainWindow.closeEvent` saves settings, then calls `PlayerWidget.shutdown`, cancels playlist and EPG loading, and waits up to 2 seconds (`QThreadPool.waitForDone`) for background tasks. `PlayerWidget.shutdown` is idempotent: it stops the reconnect timer, stops the VLC player, leaves fullscreen and hides/schedules deletion of the fullscreen window, then releases the VLC player. VLC errors during shutdown are logged by exception type only. Close can therefore wait briefly if a task (such as a playlist-manager probe on the shared global pool) is still running; an in-flight HTTP request is not aborted.

## Error Handling

Domain errors live in `core/errors.py`:

- `ValidationError`
- `NetworkError`
- `ParsingError`
- `RepositoryError`

Startup errors are logged and shown as critical dialogs before the app exits. Runtime controller errors are emitted as Qt signals and shown in the UI through notifications/status messaging. Parser warnings are non-fatal and are stored on parsed playlists or EPG controller state.

## Security And Privacy

The app is local-first and has no server-side auth boundary. The main sensitive data is Xtream credentials:

- Passwords are stored in the local SQLite database for source reloads.
- `PlaylistReference.to_settings_value()` omits the password.
- Xtream logging is designed to redact passwords and avoid logging raw credential URLs.
- `app/main.py` installs `RedactingFormatter` (`core/redaction.py`) on both the console and rotating file log handlers. It applies `redact_text` to the whole formatted record, including chained tracebacks. It masks only query-style passwords and userinfo passwords; path-embedded Xtream stream passwords are not masked, so call sites must still not log channel URLs.
- On POSIX, `SQLiteConnection` creates the data directory with mode 0700 and sets `database.db` (and `-wal`/`-shm` files when present) to 0600. The directory is chmod-ed only for the default `~/.simple_iptv` location, not for a caller-supplied parent. Failures to set modes are logged as warnings. The database is not encrypted, and no modes are changed on Windows.
- Playlist and EPG URLs are passed through `core/redaction.py` (`redact_url`, `redact_text`, `redact_identity`) before they reach logs or error messages. This masks `password`/`passwd`/`pass`/`pwd` query values and basic-auth userinfo passwords. Xtream stream URLs carry credentials in the path (`/live/<user>/<password>/<id>`), so do not log channel URLs.

Do not add logging that prints raw Xtream passwords, full authenticated URLs, or local database contents.

## Important Decisions

- Keep domain/service code independent from PyQt imports where practical.
- Keep UI-only concerns in `ui/`, not in repositories or parsers.
- Preserve source-aware channel identity for favorites and history.
- Preserve `QListView` plus `QAbstractListModel` channel virtualization for large playlists.
- Keep external source loading behind services/controllers rather than calling HTTP/parsers directly from widgets.

## Architecture Risks

- HTTP requests still rely on blocking `requests` calls. They run in background tasks, but cancellation cannot forcibly stop an in-flight request.
- SQLite schema migrations are embedded in startup code rather than external migration files.
- Xtream-compatible providers vary in response shape and transport behavior.
- VLC embedding is platform-sensitive and may behave differently under Linux Wayland, macOS, and Windows setups.
- Tests cover important seams, but there is no full app-level integration suite. CI runs pytest (Python 3.12 and 3.14, offscreen Qt), ruff, and a blocking mypy error-count ratchet on pull requests and pushes to `main`; mypy errors are not yet zero.
