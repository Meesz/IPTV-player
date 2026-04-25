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

## Persistence Model

The default database path is:

```text
~/.simple_iptv/database.db
```

`SQLiteConnection` initializes and migrates tables at startup. Startup fails fast if database initialization fails.

Main tables:

- `settings` - string key/value settings, including legacy compatibility keys.
- `playlists` - saved playlist references, source identity, Xtream credentials, channel count, last status, and last error.
- `favorites` - source-aware favorites keyed by URL and playlist path.
- `recent_channels` - recent playback history keyed by URL and playlist path.
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
- Tests cover important seams, but there is no full app-level integration suite or CI test job yet.
