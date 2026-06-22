# Refactoring Walkthrough

This note records the high-level v2 refactor direction. For current architecture details, use [docs/architecture.md](docs/architecture.md). For setup and commands, use [README.md](README.md) and [docs/development.md](docs/development.md).

## Refactor Goal

The app was moved toward a layered desktop architecture:

- `app/` wires dependencies and starts the Qt application.
- `core/` owns domain models, errors, and services.
- `infra/` owns side effects such as SQLite, parsers, HTTP providers, and VLC.
- `ui/` owns windows, widgets, dialogs, controllers, and styling.

The important maintenance rule is that UI widgets should not directly manage persistence, playlist parsing, Xtream HTTP calls, or VLC setup. Those concerns should stay behind controllers, services, repositories, providers, parsers, and playback infrastructure.

## Current Dependency Shape

```text
app/main.py
  -> repositories, services, controllers
  -> ui/windows/main_window.py
      -> ui/controllers/*
          -> core/services/*
              -> infra/db, infra/parsers, infra/providers
      -> ui/widgets/player_widget.py
          -> infra/playback/vlc_backend.py
```

## Notable Outcomes

- Playlist, EPG, settings, favorites, and history behavior now have service/repository seams.
- Playlist and EPG loading are started from controllers and run in background tasks.
- The channel list uses a model/delegate list view for large playlist performance.
- Playback is split between VLC infrastructure and the player widget UI.
- Settings and source metadata are persisted in SQLite instead of being only in memory.

## Verification Pointers

Useful checks for future refactors:

```bash
python -m pytest -q
ruff check .
ruff format --check .
python -m compileall app core infra ui tests
```

If Qt or VLC runtime dependencies are missing locally, document the limitation in the change summary rather than claiming full verification.
