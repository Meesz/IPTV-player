# Roadmap

This roadmap separates confirmed maintenance direction from speculative product ideas. It should not be read as a release commitment.

## Immediate Fixes

- **Dependency and tooling cleanup**: runtime pins in `requirements.txt` were audited and bumped for known advisories (PyQt6 and python-vlc unchanged), and Dependabot (`.github/dependabot.yml`) now checks pip and GitHub Actions weekly. Remaining: review whether every pinned dependency is still needed, especially development and packaging tools.
- **CI coverage**: CI runs pytest (Python 3.12 and 3.14), ruff, and mypy on pull requests and pushes to `main`; mypy is a blocking error-count ratchet (maximum recorded in `.github/workflows/lint.yml`). Remaining gaps: mypy errors are not yet zero, pushes to other branches do not trigger CI, and there is no app-level integration suite.
- **Packaging decision**: decide whether the app will ship as source-only, py2app, PyInstaller, platform packages, or another installer format.
- **Document packaging only after it exists**: avoid adding release commands until the checked-in configuration supports them.
- **Broaden regression coverage**: service-level playlist switching (`tests/test_playlist_switching.py`), fullscreen round-trips (`tests/test_player_fullscreen.py`), and headless favorites/history wiring (`tests/test_main_window_wiring.py`) are covered. Remaining: playlist switching through the UI and player state changes against real VLC playback.

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
- **Move Xtream passwords to the OS keychain** (via `keyring`; needs a new dependency). Whole-database encryption is not planned: with no master password the key would live next to the database, so it adds a native dependency (SQLCipher) without real protection. The password is currently stored in plain text in `playlists` and is also embedded in the path of Xtream channel URLs stored in `favorites` and `recent_channels`, so the work needs:
  - a keychain-backed credential store, with `playlists` keeping only a reference;
  - Xtream channel URLs persisted without the password and rebuilt at load/play time, which changes how `(url, playlist_path)` identity is stored;
  - a migration that rewrites existing rows and moves existing passwords into the keychain;
  - an explicit fallback when no keychain backend is available (e.g. headless Linux without Secret Service).

## Long-Term Ideas

These are speculative and should not be documented as current product scope:

- Cloud sync or multi-device state.
- Provider-specific integrations beyond the generic Xtream-compatible API.
- Recording, catch-up TV, or timeshift features.
- Remote-control or companion-device support.
- A plugin system for parsers/providers.
- A web or mobile client.

## Completed Work

Completed Phase 3 items are recorded in the archived [Phase 3 status note](archive/phase3.md). Implemented scope is listed in [product.md](product.md).
