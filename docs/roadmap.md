# Roadmap

This roadmap separates confirmed maintenance direction from speculative product ideas. It should not be read as a release commitment.

## Immediate Fixes

- **Dependency and tooling cleanup**: review whether every pinned dependency in `requirements.txt` is still needed, especially development and packaging tools.
- **CI coverage**: add a pytest job once the Qt/PyQt6 test environment is reliable in CI.
- **Packaging decision**: decide whether the app will ship as source-only, py2app, PyInstaller, platform packages, or another installer format.
- **Document packaging only after it exists**: avoid adding release commands until the checked-in configuration supports them.
- **Broaden regression coverage**: add tests for playlist switching, fullscreen transitions, favorites/history interactions, migration failures, and player state changes.

## Short-Term Improvements

- Improve user-facing diagnostics for playlist parse warnings, EPG warnings, and Xtream provider failures.
- Make background cancellation clearer in the UI and document which operations are cooperative.
- Add more source metadata in the UI, such as last EPG source, last playlist validation error, and parse warning counts.
- Harden fullscreen behavior so future UI additions are less likely to break player restore behavior.
- Continue testing Linux Wayland/XWayland playback embedding and document the known-good combinations.

## Medium-Term Features

- Add a more explicit source detail view for file, URL, and Xtream sources.
- Improve EPG matching visibility so users can see why a channel does or does not have current program data.
- Add import/export for local app data, excluding or clearly warning about credentials.
- Add a real packaging and release workflow after the chosen platform strategy is implemented.
- Consider external migration files if SQLite schema changes become more frequent.

## Long-Term Ideas

These are speculative and should not be documented as current product scope:

- Cloud sync or multi-device state.
- Provider-specific integrations beyond the generic Xtream-compatible API.
- Recording, catch-up TV, or timeshift features.
- Remote-control or companion-device support.
- A plugin system for parsers/providers.
- A web or mobile client.

## Recently Completed Phase 3 Work

The old Phase 3 backlog included several items that are now implemented:

- Database initialization fails fast and startup errors show a dialog.
- Channel/favorite identity is source-aware.
- EPG parsing, persistence, and current-time handling are separated more cleanly.
- XMLTV parsing supports gzip and namespace-tolerant child lookup.
- Playlist and EPG loading run through background controller tasks.
- Additional UI state is persisted.
- Channel rows use a virtualized model/delegate list.
- Player controls include retry, mute, fullscreen, copy URL, and channel info surfaces.
- Playlist manager validation/testing is implemented.
- Xtream credentials and generated live stream URLs are normalized and encoded.

See [phase3.md](phase3.md) for the status note that replaced the stale backlog.
