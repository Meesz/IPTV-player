# STATUS

## Current goal
Bring mypy to zero errors and lock CI at zero (branch `chore/mypy-zero`, PR open against `main`).

## Done
- mypy: 75 → 0 errors across `app core infra ui` without `type: ignore` or `cast()`.
- `Settings.with_updates` now uses `dataclasses.replace` (unknown keys ignored,
  `last_epg_xtream_identity` coerced to `str`); covered by
  `test_settings_with_updates_ignores_unknown_keys_and_coerces_epg_identity`.
- CI `MYPY_MAX_ERRORS` set to 0 in `.github/workflows/lint.yml`; docs (README, AGENTS.md,
  `docs/development.md`, `docs/architecture.md`, `docs/roadmap.md`) updated.

## Next steps
1. Merge the mypy-zero PR once CI is green.
2. Optional: enable mypy `--check-untyped-defs` (notes at `ui/dialogs/playlist_manager_dialog.py:87`,
   `ui/widgets/left_panel.py:206`).
3. Quick win: use `defusedxml` for XMLTV parsing (needs a new dependency; ask first).
4. Larger: move Xtream passwords to the OS keychain (see `docs/roadmap.md` Medium-Term).

## Open decisions
- Packaging strategy (source-only vs PyInstaller etc.) is undecided.
- Logo disk cache and Xtream catalogue cache are deferred by the user.

## Gotchas
- Use `.venv/bin/python`, `.venv/bin/ruff`, `.venv/bin/mypy`; the system python lacks PyQt6/ruff/mypy.

## Verify
```
.venv/bin/ruff check . && .venv/bin/ruff format --check .
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
.venv/bin/mypy app core infra ui   # expect "Success: no issues found"
```
