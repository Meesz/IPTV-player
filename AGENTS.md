# AGENTS.md

Simple IPTV Player: PyQt6 desktop app that loads M3U/Xtream live TV sources and XMLTV EPG,
plays through native VLC, and stores local state in SQLite. No backend, accounts, sync, or
packaging/release workflow. Entry point: `app/main.py` (`python -m app.main`).

## Map

| Path | Owns |
|------|------|
| `app/` | Process startup and dependency wiring |
| `core/` | Models (`models.py`), domain errors, services, `redaction.py` |
| `infra/` | SQLite repositories + embedded migrations (`db/sqlite_connection.py`), M3U/XMLTV parsers, Xtream client, VLC setup (`playback/vlc_backend.py`) |
| `ui/controllers/` | Qt signal orchestration and background tasks |
| `ui/widgets/`, `ui/windows/`, `ui/dialogs/`, `ui/styles/`, `ui/utils/` | Presentation |
| `tests/` | Flat pytest suite; `conftest.py` provides the `qapp` fixture, sets offscreen Qt, and redirects `Path.home()` to a temp dir for every test |

## Commands

Run from the repo root inside the project virtualenv (setup in `README.md`).
Test/lint tools come from `requirements-dev.txt`; `requirements.txt` is runtime-only.

| Task | Command |
|------|---------|
| Focused tests | `python -m pytest -q tests/test_<area>.py` |
| Full tests | `python -m pytest -q` |
| Lint / format check | `ruff check .` / `ruff format --check .` |
| Type check (CI ratchet: count must not rise) | `mypy app core infra ui` |
| Run app (GUI; writes `~/.simple_iptv/` including `iptv_player.log`; may use network) | `python -m app.main` |

CI (PRs and pushes to main; tests on 3.12 + 3.14) runs ruff check, ruff format --check, pytest, and a mypy error-count ratchet.
Ruff config and rule rationale live in `pyproject.toml`; pre-commit runs ruff on commit.

## Rules

- Widgets/windows/dialogs go through controllers/services; they must not call SQLite
  repositories, parsers, or Xtream HTTP directly. `tests/test_layer_boundaries.py` enforces
  this at the import level.
- Native VLC stays behind `infra/playback/vlc_backend.py` and `ui/widgets/player_widget.py`.
  `python-vlc` is not VLC; tests must not need libvlc (CI has none).
- Channel identity is `(url, playlist_path)`; keep it source-aware.
- Keep the channel list virtualized (`QListView` + `QAbstractListModel` +
  `QStyledItemDelegate`); never per-row widgets.
- Never log Xtream passwords or channel URLs. `core/redaction.py` masks only userinfo and
  query secrets; Xtream stream URLs carry the password in the path.
  `PlaylistReference.to_settings_value()` intentionally omits the password.
- SQLite migrations are embedded in `SQLiteConnection`; there are no migration files.
- Tests use `tmp_path` databases and mocked `requests`; never touch `~/.simple_iptv/`.
  Prefer service/repository/controller tests over anything needing a media runtime.
- Prefer explicit validation errors over silent fallbacks.
- Background cancellation drops stale results but cannot abort an in-flight `requests` call.
- Do not change `requirements*.txt`, `pyproject.toml`, `.github/`, or
  `.pre-commit-config.yaml` unless asked.
- Docs-only tasks do not touch application code. Update docs when commands, setup,
  architecture, runtime behaviour, or roadmap status change. Never document cloud sync,
  recording, installers, or backend APIs as implemented.
- If PyQt6/VLC is unavailable, report exactly which check could not run.

## Read on demand

| Need | Read |
|------|------|
| Layers, data flow, persistence, playback, error handling | `docs/architecture.md` |
| Setup, env vars, test workflow, debugging | `docs/development.md` |
| Implemented scope vs non-goals | `docs/product.md` |
| Planned work | `docs/roadmap.md` (`docs/phase3.md` is historical; do not revive it) |
| User-facing setup and limitations | `README.md` |

## Avoid unless the task is about them

- `repomix-output.xml` (~360 KB generated dump), `*.log`, `.venv/`, `*_cache/`, `__pycache__/`.
- `docs/archive/`: point-in-time audit reports and the refactor walkthrough, not current guidance.
- Large files: read targeted ranges of `tests/test_models_and_services.py`,
  `ui/windows/main_window.py`, and `ui/styles/themes.py` (mostly stylesheet data).

## Context efficiency

- Search with `rg` and open the narrowest relevant files first; do not read the whole repo.
- Do not print whole large files, logs, or generated artifacts; redirect verbose output to a
  temp file and inspect the relevant part.
- Run the focused test file first, then the full suite and ruff before finishing.
- Do not reread unchanged files you already understand.
- Use subagents only for substantial isolated exploration or independent verification.
- Use `ruff format` / `ruff check --fix` for mechanical fixes instead of hand-editing.
- Keep task-specific findings out of this file; add only durable repository facts.
