# AGENTS.md

Guidance for Codex and other coding agents working in this repository.

## Project Overview

Simple IPTV Player is a PyQt6 desktop IPTV player. It loads local/remote M3U playlists and Xtream-compatible live TV sources, imports XMLTV EPG data, plays streams through native VLC, and persists local state in SQLite.

There is no web backend, account system, cloud sync, or configured packaging release workflow.

## Read First

- `README.md` - user-facing setup, commands, current features, and limitations.
- `docs/architecture.md` - layer boundaries, data flow, persistence, playback, and error handling.
- `docs/development.md` - local setup, commands, test expectations, and debugging notes.
- `docs/product.md` - implemented product scope versus non-goals.
- `docs/roadmap.md` - current future-work tracking.
- `docs/phase3.md` - status of the old Phase 3 backlog.

## Commands

Run from repo root.

| Task | Command |
|------|---------|
| Install dependencies | `pip install -r requirements.txt` |
| Install pytest if missing | `pip install pytest` |
| Run app | `python -m app.main` |
| Run tests | `python -m pytest -q` |
| Run CI lint locally | `pylint --fail-under=9.5 $(git ls-files '*.py')` |
| Syntax check | `python -m compileall app core infra ui tests` |

The GitHub Actions workflow currently runs Pylint only. Do not claim CI test coverage unless a pytest workflow exists.
`pytest` is used by the test suite but is not currently pinned in `requirements.txt`.

## Architecture Boundaries

- `app/` wires the process and top-level dependencies.
- `core/` should stay focused on models, service logic, and domain errors.
- `infra/` owns SQLite, parsers, HTTP provider clients, and VLC setup.
- `ui/controllers/` owns Qt signal orchestration and background task handling.
- `ui/widgets/`, `ui/windows/`, and `ui/dialogs/` own UI presentation and interactions.

Do not make widgets talk directly to SQLite repositories, M3U/XMLTV parsers, Xtream HTTP calls, or VLC initialization when an existing controller/service/infrastructure boundary already exists.

## Code Style Expectations

- Follow the existing straightforward Python style.
- Use typed dataclasses and service methods where the repo already uses them.
- Keep comments short and useful.
- Prefer explicit validation errors over silent fallbacks.
- Preserve source-aware channel identity through `(url, playlist_path)`.
- Preserve channel list virtualization through `QListView`, `QAbstractListModel`, and `QStyledItemDelegate`.
- Keep native VLC handling behind `infra/playback/vlc_backend.py` and `ui/widgets/player_widget.py`.

## Testing Expectations

- Run `python -m pytest -q` after behavior changes when dependencies are available.
- Run focused pytest files for narrow changes before the full suite when useful.
- Run `pylint --fail-under=9.5 $(git ls-files '*.py')` before PR-like work.
- If PyQt6 or VLC dependencies are unavailable, say exactly what prevented verification.
- Prefer service/repository/controller tests for behavior that does not need a real media runtime.

## Documentation Expectations

- Update docs when commands, architecture, setup, runtime behavior, or roadmap status changes.
- Keep implemented features separate from planned features.
- Do not revive stale Phase 3 backlog claims as current future work.
- Do not invent packaging, deployment, API, or provider capabilities.

## Known Traps

- `python-vlc` is not VLC. Native VLC must be installed separately.
- Xtream passwords are stored locally in SQLite and must not be logged.
- `PlaylistReference.to_settings_value()` intentionally omits Xtream passwords.
- Linux Wayland playback embedding may require XWayland.
- Background playlist/EPG cancellation ignores stale results but cannot always stop an in-flight `requests` call immediately.
- SQLite migrations are embedded in `SQLiteConnection`, not external migration files.
- `requirements.txt` includes development tools; it is not split into runtime/dev dependency groups.

## Do Not

- Do not modify application code for documentation-only tasks.
- Do not change package files, CI, or dependency pins unless explicitly asked.
- Do not log raw Xtream credentials or authenticated stream URLs.
- Do not replace the virtualized channel list with per-row widgets for large playlists.
- Do not document cloud sync, recording, packaged installers, or backend APIs as implemented.
