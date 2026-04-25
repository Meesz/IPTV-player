# Product Notes

## Purpose

Simple IPTV Player gives a desktop user one place to manage IPTV channel sources, inspect program metadata, and play live streams locally. It is optimized for personal desktop use with local persistence rather than accounts or cloud-backed libraries.

## Target Users

- Users who have M3U/M3U8 playlist files or playlist URLs.
- Users with Xtream-compatible IPTV credentials.
- Users who want XMLTV EPG data beside channels and in the now-playing view.
- Developers maintaining a small PyQt6 media application.

## Core Problem

IPTV sources often come as large playlists with inconsistent metadata, unstable stream URLs, and optional EPG files. The app currently focuses on making those sources browseable, searchable, playable, and persistent across desktop sessions.

## Current Scope

The app currently supports:

- Local file and HTTP(S) playlist sources.
- Xtream-compatible live TV sources.
- Playlist source validation and duplicate detection.
- XMLTV EPG import from local files or URLs, including gzip-compressed XMLTV files.
- Channel browsing by category, search, and sort mode.
- Large-list rendering through a virtualized list view.
- VLC-backed live playback.
- Favorites and recent playback history.
- Persisted local settings and UI state.

## Non-Goals

- No hosted backend or API server.
- No user accounts, authentication, or subscription management.
- No cloud sync.
- No built-in IPTV provider.
- No bundled VLC runtime.
- No recording, timeshift, or catch-up TV implementation.
- No official packaged installer workflow in the repo.

## User Flows

### Add and load a playlist

1. Open **File -> Playlist Manager** or use `Ctrl+P`.
2. Add a local file, HTTP(S) URL, or Xtream source.
3. Optionally test the source.
4. Load the selected source into the main channel list.
5. The app stores source metadata and the last loaded source in SQLite.

### Load EPG data

1. Load an XMLTV file from the EPG menu, or enter an EPG URL in the toolbar.
2. The app downloads/parses the source in a background task.
3. Parsed programs are cached in SQLite and current program data appears in the channel list and now-playing area when channel IDs match.

### Browse and play channels

1. Select a category or tab from the left panel.
2. Search within the current category or across the full playlist.
3. Sort by name, group, or favorites-first.
4. Double-click a channel to play it, or enable single-click playback.
5. Use the player controls for stop, retry, mute, fullscreen, favorite, volume, copy URL, and channel info.

### Continue later

1. Close the app.
2. On next launch, settings and library state are read from `~/.simple_iptv/database.db`.
3. The app restores UI preferences such as theme, window size, splitter sizes, active tab, search text, selected category, sort mode, mute state, and recent channels.

## Implemented Features

- Source-aware channel identity through `(url, playlist_path)` so the same stream URL can exist in multiple sources.
- Playlist source metadata with source type, identity, channel count, load status, and last error.
- Xtream source normalization, authentication, category fetch, live channel fetch, HTTPS fallback, encoded playback URLs, and redacted logging.
- XMLTV parsing with namespace-tolerant child lookup, gzip support, UTC-aware program times, and parse warnings for invalid program dates.
- M3U parsing with multiple encodings, double/single-quoted attributes, numeric metadata warnings, and orphan stream warnings.
- Background playlist and EPG loading with stale worker result suppression.
- Virtualized rich channel rows with logo placeholders, badges, current program text, and offscreen paint coverage.
- Startup error dialogs for database/bootstrap failures and VLC-unavailable warnings.

## Planned Features

Confirmed near-term direction is maintenance and product hardening, not a new product surface:

- Clean up dependency/tooling drift.
- Decide and document a real packaging/release workflow.
- Add more integration coverage around playlist switching, full playback UI flows, fullscreen, and persistence migrations.
- Improve source diagnostics, parse warning visibility, and user-facing failure messages.
- Continue hardening playback embedding, especially on Linux Wayland/XWayland setups.

Speculative ideas are tracked separately in [roadmap.md](roadmap.md).

## Success Criteria

- A new user can install dependencies, launch the app, add a source, load EPG data, and play a stream without reading code.
- A maintainer can identify where source loading, parsing, persistence, playback, and UI state live.
- Large playlists remain browseable without per-row widget creation.
- User data survives restarts and can be reset locally.
- Credentials and stream URLs are not accidentally exposed in logs.
- Roadmap items are not confused with implemented behavior.

## Known Product Risks

- The app depends on native VLC availability and platform-specific video embedding.
- Xtream credentials are saved locally in SQLite and are not encrypted.
- IPTV provider behavior varies widely; M3U, XMLTV, and Xtream-compatible responses can be malformed or non-standard.
- Network cancellation is cooperative and may wait for current HTTP timeouts.
- There is no official distribution path yet, so users currently run from source.
