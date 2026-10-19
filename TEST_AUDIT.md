# Test Suite Audit — Simple IPTV Player

- **Mode:** AUDIT (no test or production code changed)
- **Scope:** FULL_SUITE
- **Mutation budget:** 10 (10 used, plus 1 harness sanity mutant)
- **Date / baseline:** 2026-10-17, branch `v2`, HEAD `2a4bf2b`, clean working tree

---

## 0. Remediation status (follow-up run, 2026-10-17)

The findings below describe the suite **as audited at `2a4bf2b`**. A follow-up run
(`.claude/orchestration/runs/20261017T152246Z-test-improve/`) addressed them. The changes are uncommitted.

**Overall result**
- Suite size: 80 tests → **221 tests**.
- All 10 audit mutants are now **killed**. This was re-run on the final tree; it was 2/10 before.
- The final gate passed 5 times in a row with no segfaults (Python 3.14 locally).

| Finding | Status | Where |
| --- | --- | --- |
| F1 M3U URL credential leak (confirmed defect) | **Fixed + tested.** New `core/redaction.py` (`redact_url`, `redact_text`, `redact_identity`) used by `PlaylistService`, `EPGService` and the `PlaylistRepository` error logs. Also covers bad-port URLs and `passwd`. | `tests/test_credential_redaction.py` |
| F2 restart round trip (M1, M2) | **Tested.** Real SQLite, two process lifetimes; legacy fallback matrix. | `tests/test_restart_restore.py` |
| F3 Xtream validation/auth (M3, M4) | **Tested** | `tests/test_xtream_validation.py` |
| F4 async failure/cancel (M8), false pragma | **Tested.** Real `BackgroundTask.run`; pragma comment removed. | `tests/test_async_controllers.py` |
| F5 EPG now/next and routing (M5) | **Tested** | `tests/test_epg_now_next.py` |
| F6 `MainWindow` wiring | **Tested.** Headless window, VLC disabled: load, play, history, favourites, save on close, restart. | `tests/test_main_window_wiring.py` |
| F7 URL success/retries/order (M6, M7) | **Tested** | `tests/test_playlist_url_and_query.py` |
| F8 legacy favourites migration | **Tested** | `tests/test_favorites_migration.py` |
| F9 misleading tests | **Fixed.** Renamed or strengthened (settings reload, right-panel states, delegate pixel check, MainController test renamed). | `tests/test_models_and_services.py` |
| F10 brittle tests | Partly. The `PlayerWidget`/`RightPanel` tests still use `SimpleNamespace` fakes, because a real `PlayerWidget` needs VLC. The `MainWindow` test now covers the real wiring. | — |
| F11 redundant tests | **Removed:** `tests/test_imports.py` and 2 duplicate parser tests | — |
| Defect: stale `last_playlist_path` after an Xtream source | **Fixed + tested** via `SettingsController.save_active_playlist`. It writes the legacy path keys first and identity last, and clears the path keys for Xtream. | `ui/controllers/settings_controller.py` |
| Defect: EPG overlapping-load cache race | **Open** (report only, by decision) | — |
| CI runs on pull requests only | **Open.** `.github/` was not changed, by decision; open a PR for `v2` instead. | — |

**Remaining risks**
- Favourites and history repositories log raw `channel.url` on DB failure. Xtream stream URLs embed credentials in the path, which `redact_url` does not mask.
- `NetworkError.__cause__` keeps the unredacted `requests` message. This is safe today because only `str(exc)` reaches the UI.
- A URL-load cancel after download surfaces as `ParsingError`.
- Importing `app.main` makes the test suite write `./iptv_player.log`. This is pre-existing.
- Not run on Python 3.12, which CI uses.

---

## 1. Executive assessment

The suite is **green (80/80) but protects the critical workflows much less than the pass count suggests.**

- **Where it is strong:** pure parsing and persistence logic that is tested against a real temporary SQLite file:
  - M3U and XMLTV parsing
  - SQLite schema migration
  - source-aware channel identity
  - repository round-trips
  - credential redaction for the Xtream client and EPG loader

  Both control mutants in these areas were killed immediately.
- **Where it is weak:** everything that decides whether the app actually works for a user across a session:
  - restoring the last playlist on restart
  - rejecting bad credentials
  - async failure and cancellation
  - EPG "now playing" from memory
  - the whole `MainWindow` wiring (channel → play, favourites, history, settings saved on close)

  **All 8 non-control mutants survived: 7 aimed at Critical/High behaviour and 1 at Medium (sort order).** Each survivor was then shown to change observable behaviour (section 5), so none of them is an "equivalent mutant".
- **The audit found one live security defect.** When an M3U **URL** playlist fails to download, the playlist password ends up in the log file 4 times and in the error message shown to the user. This breaks an invariant stated in `AGENTS.md`. The existing redaction tests cover only Xtream and EPG, which creates false confidence.
- **CI does not protect this branch.** Both workflows run only `on: [pull_request]`. `v2` is 247 commits ahead of `main`, and no push to it triggers CI. I could not check whether a PR is open for `v2` because the GitHub integration failed to connect.

**Overall rating:** a good unit/repository foundation, but low protection against regressions in critical workflows. Most of the risk sits at the controller/window boundary and on negative paths, not in the parsers.

---

## 2. Test architecture and commands actually used

| Aspect | Finding |
| --- | --- |
| Framework | pytest (`pyproject.toml` → `testpaths = ["tests"]`, no markers, no addopts, no `conftest.py`) |
| Tests collected | 80 in 7 files (`pytest --co`). All 7 files execute; none are dead or skipped. |
| Levels present | **Unit:** models, parsers, static helpers. **Integration with real SQLite (`tmp_path`):** repositories, migration, playlist switching, settings reload. **Controller:** Qt controllers with the thread pool *stubbed*. **Widget:** offscreen Qt for `LeftPanel`, dialogs, notifications; some widget tests use `SimpleNamespace` fakes. |
| Levels absent | No `MainWindow` test. No end-to-end/startup test with a real window. No libVLC (unavailable in CI, which is acceptable). No test runs a real `QThreadPool` worker. |
| HTTP | `requests.get` / `session.get` monkeypatched; no network |
| Qt | `QT_QPA_PLATFORM=offscreen`. Only `test_models_and_services.py` sets it itself; the other files are Qt-free by design. |
| CI | `.github/workflows/tests.yml` (pytest) and `lint.yml` (ruff + non-blocking mypy), Python 3.12, **pull_request only** |
| Local interpreter | `.venv/bin/python` = **3.14.8**. CI uses 3.12, so version-specific behaviour was not checked locally. |

Commands run (all from the repo root):

| Command | Result |
| --- | --- |
| `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q --co` | 80 collected |
| `.venv/bin/ruff check .` | PASS |
| `.venv/bin/ruff format --check .` | PASS (61 files) |
| `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q` | PASS, 80 passed in 0.33 s (baseline and final) |
| `.venv/bin/mypy app core infra ui` | 59 errors in 10 files. Pre-existing and non-blocking in CI; reported, not judged. |
| Mutation harness (scratchpad copy, see section 5) | 10 mutants plus 1 sanity mutant; run with the same pytest command inside the copy |
| Leak probe and 8 non-equivalence probes (scratchpad scripts) | See sections 5 and 7 |

Not executed: the GUI (`python -m app.main`). It writes to `~/.simple_iptv/` and uses VLC and the network, so it needs explicit approval. No test needs it.

---

## 3. Behavioural risk map and test mapping

Protection levels:
- **Strong:** a realistic regression fails a test.
- **Partial:** some regressions fail a test.
- **Weak:** the area is exercised but the assertions miss realistic regressions.
- **None:** no test executes the behaviour.

| # | Behaviour | Risk | Production path | Tests | Protection |
| --- | --- | --- | --- | --- | --- |
| C1 | Load a file playlist and tag channels with source identity `(url, playlist_path)` | Critical | `core/services/playlist_service.py:36-88, 508-510` | `test_playlist_switching.py` (3), `test_playlist_service_assigns_channel_source_path` | **Strong** (M10 killed by 3 tests) |
| C2 | Load a URL playlist (download → temp file → parse → cleanup) | Critical | `playlist_service.py:276-320, 388-408` | `test_playlist_service_handles_download_failure` (failure only, private method) | **Weak**. The success path, retry count and temp-file cleanup are untested (M6 survived). |
| C3 | Load an Xtream source (auth → categories → streams → HTTPS upgrade) | Critical | `infra/providers/xtream_client.py`, `playlist_service.py:322-386` | 9 client/service tests | **Partial**. Happy path and transport are good; the auth *decision* is weak (M4 survived). |
| C4 | Restore the last playlist on restart (persist on load → settings → `MainController.start` → saved reference including the Xtream password) | Critical | `ui/windows/main_window.py:363-405`, `core/services/settings_service.py:211-258`, `ui/controllers/main_controller.py` | `test_main_controller_restores_xtream_source` (all fakes) | **Weak/None** end to end (M1 and M2 survived) |
| C5 | Credentials never reach logs or UI errors | Critical | `xtream_client.py:315-334`, `core/services/epg_service.py:141-175`, **`playlist_service.py:47-51, 82-87, 307-309, 399-408`** | `test_credential_redaction.py` (8) plus 3 Xtream log tests | **Strong for Xtream/EPG; none for M3U URL. Defect confirmed (section 7).** |
| C6 | Channel activation → `PlayerWidget.play` → saves last channel and records history | Critical | `main_window.py:487-517`, `ui/widgets/player_widget.py:169-197` | none | **None** |
| C7 | SQLite migration keeps user data | Critical | `infra/db/sqlite_connection.py:161-287` (playlists), `:132-159` (favourites) | `test_sqlite_migration.py` (3), `test_playlist_repository_migrates_legacy_rows` | **Strong for playlists; none for the legacy favourites table** |
| H1 | Xtream input validation (URL, username, password, output) | High | `playlist_service.py:417-443` | `test_playlist_service_validates_xtream_reference` (success only) | **Weak** (M3 survived) |
| H2 | Stale or cancelled async results are ignored (playlist and EPG) | High | `ui/controllers/playlist_controller.py:186-211`, `ui/controllers/epg_controller.py` | 2 stale-*success* tests, thread pool stubbed | **Partial**. The failure path is unprotected (M8 survived); cancel signal and progress paths are untested. |
| H3 | EPG "now playing" and upcoming | High | `core/models.py:358-375` (memory), `infra/db/epg_repository.py` (DB), `epg_service.py:109-131` (routing) | DB path: 2 tests; memory path: indirect only | **DB strong; memory weak** (M5 survived); routing untested |
| H4 | Favourites, source-aware | High | `infra/db/favorites_repository.py`, `ui/controllers/favorites_controller.py`, `main_window.py:611-617` | `test_favorites_repository_is_source_aware` | **Repository strong; controller and window none** |
| H5 | Playlist library management (duplicates, active-playlist guard, metadata) | High | `playlist_service.py:162-209`, `infra/db/playlist_repository.py` | 7 tests with real SQLite | **Strong** |
| H6 | UI state saved and restored (window size, splitter, category, search, mute) | High | `settings_service.py`, `main_window.py:204-216, 770-790` | `test_settings_service_persists_extended_ui_state` (real reload) | **Service partial; `closeEvent` save and apply-on-start none** |
| H7 | Player reconnect backoff and cap | High | `player_widget.py:258-289` | `test_player_retry_flow_stops_at_cap_and_resets_on_success` (`SimpleNamespace` fake) | **Partial**. The logic is checked; the real widget wiring, timer and signals are bypassed. |
| H8 | Startup error and VLC-missing dialogs | High | `app/main.py` | 2 tests with a fake `QApplication`/window | **Strong for `main()` logic** |
| M1 | Search, category filter, sort modes | Medium | `playlist_service.py:115-157, 512-538` | `test_playlist_service_uses_canonical_query_pipeline` | **Partial**. Filtering is covered; ordering is not (M7 survived). |
| M2 | M3U parser edge cases | Medium | `infra/parsers/m3u_parser.py` | 9 tests | **Strong** (some duplicated) |
| M3 | XMLTV parser (timezones, gzip, namespaces) | Medium | `infra/parsers/epg_parser.py` | 2 tests | **Strong for timezone/gzip** (M9 killed); invalid-date warnings and 12-digit dates untested |
| M4 | Recent channels history | Medium | `infra/db/history_repository.py` | `test_recent_history_round_trip` (1 row) | **Weak**. Ordering, limit and upsert are untested. |
| M5 | Playlist-manager dialog validation/test feedback | Medium | `ui/dialogs/playlist_manager_dialog.py` | 1 test (synchronous pool, private methods) | **Partial** |
| L1 | Log level, delegate paint, dialog backgrounds, imports, `Settings.with_updates` | Low | various | 6 tests | Adequate or over-tested for the risk |

**Imbalance.** About 20 tests protect parsers and Low/Medium utilities, three of them duplicates. Two Critical workflows have no protection at all: C4 restart restore end to end, and C6 channel → play. C5 is protected only partly.

---

## 4. Strongest and weakest test areas

### Strongest (effective tests)
1. **M3U parser** (`tests/test_m3u_parser.py`, parser tests in `test_models_and_services.py`). These are precise regression tests for real bugs: non-`-1` durations, commas inside quotes, missing duration, warning codes. They assert exact names, groups and warning-code sets.
2. **SQLite migration** (`tests/test_sqlite_migration.py`, `test_playlist_repository_migrates_legacy_rows`). They build real legacy schemas and assert the runtime-identity semantics (`abspath` rather than `resolve`), collision tolerance and URL rows.
3. **Source-aware identity and playlist switching** (`tests/test_playlist_switching.py`, `test_channel_identity_is_source_aware`, `test_favorites_repository_is_source_aware`). Control mutant M10 was killed by 3 independent tests.
4. **Xtream/EPG credential redaction** (`tests/test_credential_redaction.py`). Realistic exception strings with embedded URLs; checks on both log text and exception messages; covers basic-auth userinfo.
5. **XMLTV timezone handling** (`test_epg_parser_supports_namespaces_and_gzip`). Asserts an exact UTC instant, and control mutant M9 was killed.
6. **Playlist library rules** (duplicates, active-playlist guard, metadata survives import), against real SQLite.

### Weakest
1. **Restart restore (C4).** The only test is all fakes. M1 and M2 survived.
2. **`MainWindow` wiring (C6, H4, H6).** Nothing constructs `MainWindow`. Every signal connection, `closeEvent` persistence and the play path are unprotected. The scout inventory found about 15 regression-relevant behaviours there with no test.
3. **Negative paths of security-relevant decisions (H1, C3).** Only success paths are tested. M3 and M4 survived.
4. **Async failure and cancellation (H2).** Only stale *success* is tested, and the thread pool is always stubbed. M8 survived.
5. **M3U URL source (C2, C5).** No success-path test, no retry-count assertion, no redaction test, and a confirmed leak.

---

## 5. Mutation results

**How the mutants were run.** Mutants were never applied in the working tree. A pristine copy was exported with `git archive HEAD` (the tree was clean, so HEAD equalled the working tree). Each mutant was applied to a fresh copy of that export and the full suite was run inside the copy.

- **Harness validity.** A sanity mutant (`M3UParser.parse` raises) failed 13 tests in the copy. This confirms the copy's modules were the ones imported, not the checkout's.
- **No residue.** `diff -rq pristine mut` was empty after every run, and `git status` of the checkout was clean before the report was written.
- **Survivors are real.** Each survivor was run against a short probe in both the pristine and the mutated copy. The probe column shows original → mutant.

| ID | Mutation (file:line) | Behaviour | Result | Killing tests / non-equivalence probe |
| --- | --- | --- | --- | --- |
| M1 | `settings_service.py:224-226`: stop reading `last_playlist_identity` from the DB | Restart restore of Xtream/any source (C4) | **SURVIVED** | Reload after save: `'xtream::https://p::alice::ts'` → `''`. On a real restart the identity lookup is skipped and the app falls back to the legacy path, so an Xtream source is not restored. |
| M2 | `main_controller.py:21`: legacy `is_url` flag inverted | Restore of a file/URL playlist from legacy settings (C4) | **SURVIVED** | `[('/x/list.m3u', False)]` → `[('/x/list.m3u', True)]`, so a file playlist is loaded as a URL |
| M3 | `playlist_service.py:430-431`: removed "Xtream password is required" | Validation of Xtream input (H1) | **SURVIVED** | `raises ValidationError` → returns a valid XTREAM reference with an empty password |
| M4 | `xtream_client.py:297`: removed the `status in {disabled, banned}` check | Xtream auth decision (C3) | **SURVIVED** | `auth=1, status=Banned`: `raises ValidationError` → accepted |
| M5 | `models.py:364`: dropped the `< end_time` bound | EPG now-playing from memory (H3) | **SURVIVED** | At 12:00, programme 10–11: `None` → `'Old show'` (stale programme shown as live) |
| M6 | `playlist_service.py:393`: `range(1, 2)` | URL download retries (C2) | **SURVIVED** | `attempts 3` → `attempts 1` |
| M7 | `playlist_service.py:538`: default `name_asc` sort reversed | Channel list order (M1) | **SURVIVED** | `['Alpha','Bravo']` → `['Bravo','Alpha']` |
| M8 | `playlist_controller.py:198-200`: removed the stale guard in `_on_task_failed` | Stale async failure surfaced (H2) | **SURVIVED** | `errors shown: []` → `['stale failure from slow.m3u']` (an error toast for a playlist the user already switched away from) |
| M9 | `epg_parser.py:35`: timezone sign flipped (control) | XMLTV time conversion (M3) | **KILLED** | `test_epg_parser_supports_namespaces_and_gzip` |
| M10 | `playlist_service.py:510`: channels not retagged with source identity (control) | Source-aware identity (C1) | **KILLED** | `test_playlist_service_assigns_channel_source_path`, `test_switching_file_playlists_updates_current_and_retags_channels`, `test_switch_back_to_first_playlist_restores_its_channels` |

**Score:** 2 of 10 killed. Every targeted Critical/High mutant survived; both controls were killed. The suite catches regressions in the areas it was written for (parsing, identity) and misses them almost everywhere else.

---

## 6. Prioritised findings

Effort: **S** < 1 h, **M** 1–4 h, **L** > 4 h. Priority: **P0** fix now, **P1** next, **P2** later.

### F1. Missing test, with a confirmed defect: M3U URL credential redaction (P0, S + small production fix)
- **Production path:**
  - `core/services/playlist_service.py:399` and `:402` log the raw URL / raw exception on every retry.
  - `:307`, `:309`, `:407`, `:408` put the raw URL in the `NetworkError` shown in the UI.
  - `:47-51` and `:82-87` log `source_identity` (`url::<full URL>`) at INFO on every *successful* load.
  - `:207` puts `source_summary()` (the full URL) in the duplicate-playlist validation message.
- **Test path:** none. `tests/test_credential_redaction.py` covers only `XtreamClient` and `EPGService`.
- **Weakness:** the security invariant in `AGENTS.md` is enforced per loader, and the M3U URL loader was never added.
- **Escaping regression (happening today):** a probe with `http://host/get.php?username=alice&password=SuperSecret123&type=m3u_plus` and a connection error showed `LOG_LEAKS: True count 4` and `ERROR_MSG_LEAKS: True`.
- **Recommended level:** service unit test, parametrised over every network entry point.
- **Scenario:** for M3U URL, EPG URL and Xtream, check both failure (timeout, connection error, HTTP error) and success. Assert the secret is absent from `caplog.text` and from `str(exc)`, and that a mask (`***` / `%2A%2A%2A`) is present.

### F2. Missing test: restart round-trip (P0, M)
- **Production path:** `main_window.py:363-405` (`_persist_playlist_state`) → `settings_service.py:299-377` → reload `:211-258` → `main_controller.py:6-25` → `playlist_repository.get_playlist_by_identity`.
- **Test path:** `test_main_controller_restores_xtream_source` (fakes only) and `test_settings_service_persists_extended_ui_state` (does not include the identity key).
- **Weakness:** no test crosses the process-restart boundary for the active playlist. M1 and M2 survived.
- **Escaping regression:** M1. After a restart the Xtream source is not restored, or a stale file playlist loads instead.
- **Recommended level:** integration test with one SQLite file and two sets of service instances.
- **Scenario:**
  1. Save an Xtream (and a file, and a URL) reference.
  2. Save the settings payload that `_persist_playlist_state` writes.
  3. Build new `SettingsService`, `PlaylistRepository` and `PlaylistService` instances on the same DB.
  4. Run `MainController.start()` with a recording playlist controller.
  5. Assert it receives the saved reference **with the password intact**.

  Also parametrise the legacy-settings fallback matrix (`last_playlist_is_url` true/false/garbage, source type file/url).
- **Note:** `_persist_playlist_state` is business logic inside a widget. Moving it into `PlaylistController` would make it testable without `MainWindow`. That is a small refactor and needs approval.

### F3. Missing negative tests: Xtream validation and auth (P1, S)
- **Production path:** `playlist_service.py:422-433`, `xtream_client.py:283-298`
- **Test path:** `test_playlist_service_validates_xtream_reference` (success only); `test_xtream_client_auth_failure` uses `auth=0` together with `Disabled`, so the status check is never isolated.
- **Escaping regression:** M3 (empty password accepted) and M4 (banned account accepted).
- **Recommended level:** unit tests, parametrised.
- **Scenario:**
  - Validation: missing URL, non-http URL, blank username, blank password, `output="mp4"`; each raises `ValidationError` with the expected message.
  - Auth: `auth=1` with `status ∈ {Banned, Disabled}` is rejected; `auth ∈ {"1", 1, "true"}` with `Active` is accepted.

### F4. Useful but incomplete: async controller paths (P1, S–M)
- **Production path:** `playlist_controller.py:79-85, 186-211`; `epg_controller.py` (same pattern); `background_tasks.py:31-42`
- **Test path:** `test_playlist_controller_ignores_stale_worker_result`, `test_epg_controller_ignores_stale_worker_result`
- **Weakness:**
  - Only stale *success* is tested; stale failure, stale progress, `loading_cancelled` / `loading_finished` emission and `cancel_callback` semantics are not.
  - `_thread_pool.start` is always stubbed.
  - `background_tasks.py:39` says `# pragma: no cover - exercised via controller tests`, but no test runs the `except` branch of `BackgroundTask.run`. The only real `run()` call is the playlist-manager dialog test, success path, run synchronously. That comment is false confidence.
- **Escaping regression:** M8 (stale error toast).
- **Hidden interaction:** two overlapping EPG loads both reach `EPGRepository.save_all` (DELETE plus reinsert) in worker threads. The stale task checks cancellation only *between* steps (`epg_service.py:53-61`), so a stale load can overwrite the DB cache that is used after restart. This is by inspection; I did not reproduce it.
- **Recommended level:** controller tests.
- **Scenario:**
  - Stale failure: no `error_occurred`.
  - `cancel_loading(emit_signal=True)`: emits `loading_cancelled`; `cancel_callback()` becomes True.
  - Run a real `BackgroundTask` synchronously whose function raises: `error_occurred` carries the message and `loading_finished` fires.

### F5. Missing test: EPG in-memory now/next and routing (P1, S)
- **Production path:** `core/models.py:358-375`, `epg_service.py:109-131`
- **Test path:** only `test_db_upcoming_excludes_currently_airing_and_matches_memory` (in-memory upcoming as a side comparison)
- **Escaping regression:** M5 (a finished programme shown as "now").
- **Scenario:**
  - `get_current_program` at start (inclusive), mid, end (exclusive) and after.
  - `EPGService.get_program_for_channel` uses memory when the channel is loaded and falls back to the DB when it is not.
  - A successful `load_epg_from_path` populates `loaded_channels` and `last_warnings`.

### F6. Missing test: channel activation → play, and the `MainWindow` wiring (P1, M–L)
- **Production path:** `main_window.py:144-197` (signals), `:487-517` (`_play_channel`), `:611-617` (favourite toggle), `:770-790` (`closeEvent`)
- **Test path:** none
- **Escaping regression:** a broken `channel_activated` connection, `last_channel_url` no longer saved, history not recorded, or settings not saved on close. All of these pass the suite.
- **Recommended level:** one headless widget-integration test. Use a real `MainWindow` built from `tmp_path` DB services and a fake player (or `vlc_available=False` with `play` spied).
- **Scenario:**
  1. Load a 2-channel file playlist.
  2. Activate row 1: `play(url)` is called, settings hold `last_channel_url`, recent channels has 1 entry.
  3. Toggle favourite: the repository has it.
  4. Close: settings reload with the new splitter, category and search values.

### F7. Useful but incomplete: URL download and ordering (P2, S)
- **Test path:** `test_playlist_service_handles_download_failure` (private method, asserts only the exception type), `test_playlist_service_uses_canonical_query_pipeline`
- **Escaping regression:** M6 (no retries), M7 (reversed order)
- **Scenario:**
  - Count `requests.get` calls (3) and assert the temp file is deleted after a successful URL load through `load_playlist` (not `_download_with_retries`).
  - For each sort mode with at least 3 channels, assert the full order.

### F8. Missing test: legacy favourites migration (P2, S)
- **Production path:** `sqlite_connection.py:132-159`
- **Weakness:** the rename/copy/drop migration that carries existing user favourites forward is never executed by a test.
- **Scenario:** create a legacy `favorites` table without `playlist_path`, open `SQLiteConnection`, assert the rows survive with `playlist_path=''`.

### F9. Misleading tests (P1, S each)
- **`test_main_controller_restores_xtream_source`** (`test_models_and_services.py:1249`). The name promises Xtream restore, but the settings controller and playlist controller are fakes that hand back the identity. M1, which breaks exactly this restore on a real restart, survives. See section 9.
- **`test_settings_service_legacy_key_sync`** (`:337`). It never builds a second `SettingsService` and never reads the legacy keys from the repository. It asserts in-memory `get_setting` only, so the "sync" in its name is unverified. By inspection, a mutant that skips the legacy `repository.save_setting` calls would pass it; that mutant was not run because the budget was used.
- **`test_right_panel_always_clears_playback_detail`** (`:575`). The name says "always", but only the `idle` case is asserted, on `SimpleNamespace` fakes.
- **`test_channel_row_delegate_paints_offscreen_without_errors`** (`:629`). `assert not pixmap.isNull()` is always true for a 420×96 pixmap, so the test fails only if `paint` raises. Rename it or label it a crash smoke test.

### F10. Brittle implementation tests (P2, S)
- **`test_player_retry_flow_stops_at_cap_and_resets_on_success`** (`:524`). Calls three private methods on a `SimpleNamespace` stand-in. It bypasses the real `__init__` wiring (`player_widget.py:126-145`), the real `QTimer`, `play()` and signal emission. The backoff logic is checked, but any rename or refactor breaks the test without a behaviour change, and real wiring regressions go undetected.
- **`test_xtream_source_dialog_has_opaque_root`** (`:754`) and the `WA_StyledBackground` assertion in `test_playlist_manager_shows_inline_validation_and_test_results`. These are styling implementation details. Meanwhile the Xtream credential form (High risk) has no behavioural test.
- **`test_left_panel_loading_state`** reads the private `_collection_views`. **`test_notification_widget_queues_messages_and_repositions`** calls the private `_advance_queue`.

### F11. Redundant and obsolete tests (P2, S)
- `test_m3u_parser.py::test_matches_existing_basic_fixture` and `::test_matches_existing_warning_fixture` copy `test_m3u_parser_reads_channels` and `test_m3u_parser_collects_warnings_without_dropping_valid_channels` exactly. The original reason (Qt-free copies for runtimes without PyQt6) is moot now that both CI and the venv install PyQt6. Keep one copy of each.
- `test_imports.py::test_imports_smoke` asserts that classes are truthy. It can fail only on `ImportError`, which every other test file would also hit. It uses a `sys.path.append(os.getcwd())` workaround. Delete it, or keep it as an explicitly labelled smoke test.
- These 3 tests are about 4% of the count and add no protection beyond what other tests already give.

### Other defects found during the audit (by inspection, not covered by tests)
- **Xtream source, then deleted.** For Xtream sources `_persist_playlist_state` (`main_window.py:371-378`) does not update `last_playlist_path`. If the Xtream entry is later deleted from the library, restart falls back to the *previous* file/URL playlist.
- **EPG overlapping-load cache race:** see F4.

---

## 7. Confirmed defect evidence (M3U URL credential leak)

Probe (scratchpad, no repository change): `requests.get` patched to raise `ConnectionError("Max retries exceeded with url: <url>")`, then `PlaylistService.load_playlist("http://host/get.php?username=alice&password=SuperSecret123&type=m3u_plus", is_url=True)`.

```
ERROR_MSG_LEAKS: True
LOG_LEAKS: True count 4
```

The `NetworkError` text reaches the UI notification through `PlaylistController.error_occurred`. The log lines are written to `iptv_player.log`. Xtream `get.php` M3U URLs are a common way to add a provider, so this is a realistic setup. The fix belongs in production code (reuse a URL-redaction helper like `EPGService._redact_url`) and is outside this AUDIT task.

---

## 8. Highest-return improvements (ordered)

| # | Improvement | Kills / closes | Effort |
| --- | --- | --- | --- |
| 1 | Parametrised "no secret in logs or errors" test over M3U URL, EPG URL and Xtream, failure and success paths, plus the production redaction fix | F1, C5 | S + S |
| 2 | Restart round-trip integration test (Xtream/file/URL) plus the legacy fallback matrix | M1, M2, F2 | M |
| 3 | Negative validation/auth tests for Xtream | M3, M4 | S |
| 4 | Controller failure/cancel tests plus one real `BackgroundTask.run` failure test; remove the false `pragma` comment | M8, F4 | S–M |
| 5 | EPG in-memory boundaries and memory/DB routing | M5 | S |
| 6 | Headless `MainWindow` play/favourite/close test with a fake player | F6 (C6, H4, H6) | M–L |
| 7 | URL success path, retry count, temp-file cleanup; full ordering per sort mode | M6, M7 | S |
| 8 | Legacy favourites migration test | F8 | S |
| 9 | Rename or strengthen the misleading tests; delete the 3 redundant tests | F9, F11 | S |

Items 1–5 together are roughly one day of work. They would have killed 6 of the 8 surviving mutants (M1–M5, M8; M6 and M7 need item 7) and closed the confirmed leak.

---

## 9. Single most dangerous missing test

**A credential-redaction test for M3U URL playlists (F1).**

It guards a security invariant the project states in writing ("Do not log raw Xtream credentials or authenticated stream URLs"). That invariant is **violated today** in the log file and in user-visible error messages. The existing `test_credential_redaction.py` makes the suite *look* as if redaction is covered when one of the three network loaders was never included. Restart round-trip (F2) is a close second; it is a functional, not a security, failure.

## 10. Most misleading existing test

**`tests/test_models_and_services.py::test_main_controller_restores_xtream_source`.**

Its name claims the app restores an Xtream source. It actually checks only that `MainController.start()` forwards whatever a *fake* settings controller returns to a *fake* playlist controller. It never touches the SQLite-backed `SettingsService` that has to persist and reload `last_playlist_identity`, and it never touches `_persist_playlist_state`, which writes it. Mutant M1 removes that reload and therefore breaks Xtream restore on every real restart. The test still passes.

Runners-up: `test_settings_service_legacy_key_sync` (asserts in-memory state only) and `test_player_retry_flow_stops_at_cap_and_resets_on_success` (calls private methods on a `SimpleNamespace` fake).

---

## 11. Recommended testing policy going forward

1. **Regression proof.** Every bug fix lands with a test that fails on the pre-fix code. Check it by temporarily reverting the fix, as M9/M10 show for the parser and identity tests.
2. **Negative-path rule.** Every validation branch and every accept/reject decision (credentials, auth status, active-playlist guard) gets at least one *rejecting* test as well as the happy path.
3. **Persistence means reload.** A persistence test must read back through a *new* service/repository instance on the same SQLite file. In-memory assertions do not count as persistence coverage.
4. **Security invariants are parametrised.** Keep one `no secret in caplog or exception` test whose parameter list holds every network entry point. A new loader is not done until it is in that list.
5. **Mock at the boundary, not the subject.** Fake `requests`, VLC and the thread pool's *scheduling*. Do not replace the object under test with `SimpleNamespace`, and avoid calling private methods. Where a widget needs a backend, build the real widget with a fake backend.
6. **Every Critical workflow needs at least one test that crosses layers:** restart restore, channel → play, and favourite toggle, run through real controllers and SQLite.
7. **Mutation spot checks during review.** For changes to `core/`, `infra/db/`, `infra/providers/` and the controllers, the reviewer flips one key condition and confirms a test fails. Adopting a tool such as mutmut would be a dependency change and needs explicit approval.
8. **Hygiene.**
   - Split `test_models_and_services.py` (1,400 lines) by layer.
   - Remove duplicate and import-only tests.
   - Name tests after the behaviour they actually assert.
   - Keep pragma comments truthful.
9. **CI coverage of the working branch.** Make the existing workflows run on pushes to long-lived branches such as `v2`, or open a PR for `v2`, so the suite actually gates this work. Changing `.github/` needs explicit approval per `AGENTS.md`.

---

## Appendix: validation

- Final `ruff check .` PASS, `ruff format --check .` PASS, `pytest -q` 80 passed, all on the unchanged production tree. There are no pre-existing failures.
- Mutants were applied only inside a scratchpad copy. The copy diffed clean against the pristine export after every run. No production or test file in the checkout was modified.
- Files added to the checkout: `TEST_AUDIT.md` (the only path in `git status`) and the git-ignored orchestration run directory `.claude/orchestration/runs/20261017T150745Z-test-audit/` (state and work order).
- Not executed: the GUI (`python -m app.main`, which needs approval and writes to `~/.simple_iptv/`), real libVLC playback, and Python 3.12 (not installed locally; CI uses it).
- Inferred rather than executed: the scout's per-widget "would fail" judgements (section 3, `MainWindow` rows) come from reading the assertions. The EPG overlapping-load race and the stale `last_playlist_path` after an Xtream source are deleted are by inspection only.
