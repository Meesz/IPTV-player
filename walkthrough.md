# IPTV Player v2 Refactoring Walkthrough

## Overview
The IPTV Player has been refactored to a clean v2 architecture, separating concerns into Domain (`core`), Infrastructure (`infra`), and UI (`ui`) layers.

## Directory Structure
- **app/**: Application entry point (`main.py`).
- **core/**: Domain logic.
  - **models.py**: Data models (`Channel`, `Playlist`, `Settings`, etc.).
  - **services/**: Business logic (`PlaylistService`, `EPGService`, etc.).
- **infra/**: Infrastructure and side effects.
  - **db/**: Database repositories (`PlaylistRepository`, `SQLiteConnection`, etc.).
  - **parsers/**: File parsers (`M3UParser`, `EPGParser`).
  - **playback/**: VLC backend (`VLCBackend`).
- **ui/**: User Interface (Qt).
  - **windows/**: Main window (`MainWindow`).
  - **widgets/**: Reusable widgets (`PlayerWidget`, `EPGWidget`, etc.).
  - **dialogs/**: Dialogs (`PlaylistManagerDialog`).
  - **controllers/**: UI logic (`MainController`, `PlaylistController`, etc.).
  - **styles/**: Themes and styles.

## Key Changes
1. **Separation of Concerns**: UI code no longer accesses the database or VLC directly. It uses Controllers, which use Services, which use Repositories/Parsers.
2. **Dependency Injection**: Dependencies are injected from `app/main.py`.
3. **Unified Playback**: `VLCBackend` provides a clean interface for VLC, and `PlayerWidget` handles the UI aspect.
4. **Standardized Parsers**: `M3UParser` and `EPGParser` are now in `infra/parsers` and return domain models.

## How to Run
1. Ensure you have the dependencies installed (including `python-vlc` and VLC media player).
2. Run the application from the root directory:
   ```bash
   python -m app.main
   ```

## Verification
- **Imports**: Verified that all modules can be imported without errors.
- **Database**: Verified that the database initializes correctly.
- **UI**: The UI structure is in place, connecting controllers and widgets.
