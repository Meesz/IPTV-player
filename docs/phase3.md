# Phase 3 Status

This file used to be the Phase 3 backlog. It now records which Phase 3 items are implemented and which follow-up risks remain. Use [roadmap.md](roadmap.md) as the canonical future-work list.

## Completed

### Correctness and reliability

- Playback retry state now has a reconnect cap and resets after a successful playing event.
- SQLite initialization fails fast and startup failures are surfaced through a startup error dialog.
- Channel identity is source-aware through `(url, playlist_path)`, and favorites use the same distinction.
- EPG parse failures and repository persistence failures are no longer collapsed into the same parsing error path.
- EPG lookups accept an explicit current time and normalize to UTC-aware datetimes.
- Playlist manager operations validate source references, detect duplicates, and protect the active playlist from unsafe source edits/removal.

### UI responsiveness and state

- Playlist and EPG loading run through `QThreadPool` background tasks via `PlaylistController` and `EPGController`.
- Stale worker results are ignored when a newer load starts.
- More UI state is persisted, including splitter sizes, active tab, selected category, search text, sort mode, left-panel visibility, mute state, theme, and window size.
- Playback detail text is explicitly cleared on state changes.
- Channel filtering and sorting use the service-level query pipeline.

### Parsing and data quality

- XMLTV parsing supports gzip-compressed files and namespace-tolerant child lookup.
- XMLTV timestamps are normalized to timezone-aware UTC datetimes.
- M3U parsing supports multiple encodings, single-quoted and double-quoted attributes, and non-fatal parse warnings for malformed numeric metadata and orphan stream URLs.

### Product and UX

- Channel rows are rendered through a virtualized `QListView`, `QAbstractListModel`, and custom delegate.
- Channel rows can show logo placeholders, group/current program text, and live/favorite badges.
- The right panel includes playback controls for play, stop, retry, mute, fullscreen, favorite, copy URL, channel info, and volume.
- Loading and empty states exist for the main channel surfaces.
- Notifications queue and reposition on parent resize.
- Playlist manager validation feedback, test-source behavior, metadata display, duplicate detection, and active-source safeguards are implemented.
- Playlist and EPG status chips expose loading, ready, warning, and error states.

### Xtream source hardening

- Xtream credentials are normalized before use and persistence.
- Generated live stream URLs percent-encode username, password, and stream ID segments.
- Xtream authentication and live-channel fetches log redacted source summaries.
- HTTP sources can retry over HTTPS when the provider requires it.
- Saved Xtream rows are normalized on repository reads.

### Documentation and packaging cleanup

- `README.md` now describes the current `app/`, `core/`, `infra/`, and `ui/` structure.
- `MANIFEST.in` includes the current package directories.
- `requirements.txt` no longer lists PyQt5 alongside PyQt6.

## Remaining Risks

- Playback embedding can still be platform-sensitive, especially under Linux Wayland without XWayland.
- Playlist and EPG downloads use blocking `requests` calls inside background tasks. UI responsiveness is protected, but cancellation cannot forcibly terminate an in-flight request.
- SQLite schema migration logic lives in startup code rather than in explicit migration files.
- Pylint is the only configured GitHub Actions check; pytest is not run in CI.
- There is no documented packaging or release build.
- Full app integration coverage is still thin around playlist switching, fullscreen, playback events, and database migration failures.

## Current Follow-Up Direction

Use [roadmap.md](roadmap.md) for active planning. Near-term work should focus on dependency/tooling cleanup, CI test coverage, packaging decisions, diagnostics, and continued playback/platform hardening.
