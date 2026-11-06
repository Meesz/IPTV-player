# STATUS

## Current goal
Close the "defusedxml" open item (branch `chore/defusedxml`, PR against `main`).
Decision (2026-11-06): no defusedxml. Rely on expat's own protection, add a version guard and tests.

## Done
- mypy-zero: PR #44 merged to `main` (merge `949dbe6`); CI ratchet `MYPY_MAX_ERRORS` is 0.
- Measured: the stdlib EPG parser already rejects billion-laughs and quadratic-blowup payloads
  (expat 2.10 amplification limit) and external entities (ElementTree never resolves them).
  defusedxml 0.7.1 made a 40 MB guide parse ~22% slower (3.09 s → 3.78 s, pure-Python parser).
- `infra/parsers/epg_parser.py`: refuses to parse on expat < 2.4.1 (`_MIN_EXPAT_VERSION`).
- `tests/test_epg_and_settings_robustness.py`: three attack payloads + version-guard test.
- `docs/architecture.md` (EPG section) documents why defusedxml is not used.

## Next steps
1. Merge the defusedxml PR once CI is green.
2. Optional: enable mypy `--check-untyped-defs` (notes at `ui/dialogs/playlist_manager_dialog.py:87`,
   `ui/widgets/left_panel.py:206`).
3. Larger: move Xtream passwords to the OS keychain (see `docs/roadmap.md` Medium-Term).

## Open decisions
- Packaging strategy (source-only vs PyInstaller etc.) is undecided.
- Logo disk cache and Xtream catalogue cache are deferred by the user.

## Gotchas
- Use `.venv/bin/python`, `.venv/bin/ruff`, `.venv/bin/mypy`; the system python lacks PyQt6/ruff/mypy.
- Merged local branches (`chore/mypy-zero`) are not deleted unless asked.

## Verify
```
.venv/bin/ruff check . && .venv/bin/ruff format --check .
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
.venv/bin/mypy app core infra ui   # expect "Success: no issues found"
```
