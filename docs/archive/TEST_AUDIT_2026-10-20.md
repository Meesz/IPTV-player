# Test Suite Audit — Simple IPTV Player

- **Date:** 2026-10-20
- **Mode:** AUDIT. Nothing was changed except this file. Mutations ran in a scratch copy and were reverted.
- **Scope:** FULL_SUITE.
- **Mutation budget:** 10 of 10 used.

Earlier audit: `docs/archive/TEST_AUDIT.md` (point-in-time). Its M-numbered mutants are referenced in test docstrings.

---

## 1. Executive assessment

**Overall:** the suite is a strong contract suite. It protects workflows much less well.

- **Size and health.**
  - 491 tests in 27 files, about 6.6 s.
  - Everything passes; ruff is clean.
  - mypy sits exactly at the CI ratchet ceiling (75).
- **Strong where the previous audit pointed.** It reliably protects these boundaries:
  - download byte/time limits and retry policy
  - credential redaction in logged errors
  - Xtream input and auth validation
  - SQLite migrations and file permissions
  - stale-result suppression for background loads
  - now/next guide lookup
  - layer import boundaries
  
  These tests use real SQLite on `tmp_path`, a stubbed `requests`, and assertions that check behaviour.
- **Weak on stateful behaviour.** It does not protect behaviour that spans several calls or survives a restart:
  - the EPG cache lifecycle
  - per-provider guide freshness
  - names in the saved library
  - the player's reconnect state machine
  - the player's exception logging path
  
  These are exactly the parts a refactor tends to touch.
- **Mutation results.**
  - 8 targeted, realistic regressions in these areas all survived the full suite.
  - A ninth mutant also survived, but it is near-equivalent (MUT-F).
  - The positive control (MUT-J) was killed, so the harness does detect failures and the survivals are real gaps.
  - The mutants were chosen adversarially, where gaps were suspected. This is **not** a suite-wide mutation score.
- **Confirmed defect hidden by fake-based tests.**
  - The legacy branch of active-playlist restore does not work through the real settings stack.
  - 13 tests in `tests/test_restart_restore.py` say it works. They use a dict fake that exposes settings keys the real `SettingsController` never returns.
- **Smaller issues:**
  - About 6 tests protect production-dead code, and 4 more members are dead with no callers at all.
  - Two tests take about 53 % of the suite's runtime, because an app-wide stylesheet interacts with widgets leaked by earlier tests.
  - A few assertions are lenient (exception-type tuples) or vacuous (the notification queue test).

**Bottom line:** a green CI run is good evidence for parsing, validation, redaction and migrations. It is weak evidence for EPG cache correctness, player recovery, legacy restore and library naming.

---

## 2. Test architecture and commands actually used

**Stack**
- pytest, configured with `testpaths = ["tests"]` in `pyproject.toml`. The suite is flat.
- `tests/conftest.py` provides:
  - an autouse `isolated_home`, which redirects `Path.home()` to a temp directory
  - an autouse `no_retry_backoff_sleep`
  - a session-scoped `qapp` fixture, with offscreen Qt
- No libvlc. Player tests use fake VLC instances, or `no_vlc`.
- HTTP is stubbed with `monkeypatch` on `requests.get` / `Session.get`.
- Persistence uses real SQLite on `tmp_path`.

**Test levels**
- Mostly unit and service tests.
- Repository and migration integration tests against real SQLite.
- A thin wiring layer that builds a real `MainWindow` (`tests/test_main_window_wiring.py`).
  - Its `_build_window` duplicates `app.main.create_window` wiring instead of calling it.
- Qt widget, layout and rendering tests.

**CI**
- `.github/workflows/tests.yml`: pytest on Python 3.12 and 3.14.
- `.github/workflows/lint.yml` (3.12):
  - ruff check
  - ruff format --check
  - mypy error-count ratchet (`MYPY_MAX_ERRORS: "75"`)

### Commands run for this audit

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q -p no:cacheprovider --durations=8` (Python 3.14.8) | **PASS**: 491 passed in 6.62 s |
| `.venv/bin/ruff check .` | **PASS**: all checks passed |
| `.venv/bin/ruff format --check .` | **PASS**: 87 files already formatted |
| `.venv/bin/mypy app core infra ui` | Exit 1 with 75 errors in 11 files. The errors existed before this audit. **PASS** against the CI ratchet (≤ 75). |
| Per mutant, in a scratch copy: `pytest -q -p no:cacheprovider -o console_output_style=classic -rf` | Baseline 491 passed. Results in §5. |
| Delegated read-only UI review: 9 UI-scoped test files, plus `tests/test_ui_layout.py` | 143 passed and 47 passed |
| Probe scripts in the scratchpad, not in the repo: legacy-restore and URL-as-file | Behaviour confirmed (§6, F2) |
| pytest / mypy on Python 3.12 | **NOT_RUN**: interpreter not installed locally |
| Real libvlc playback, GUI run (`python -m app.main`) | **NOT_RUN**: out of audit scope. It would write `~/.simple_iptv/` and may use the network. |

---

## 3. Behavioural risk map

Strength ratings: **E** = effective, **U** = useful but incomplete, **W** = weak or missing.

### Critical

**Xtream password and stream URL never reach logs, the UI or persisted settings.**
- Tests: `test_credential_redaction.py`, `test_logging.py`, `test_main_window_wiring.py`.
- Strength: **U**.
- Logged service errors are well covered. The `PlayerWidget.play()` exception path has no test (MUT-H survived). Neither do `show_notification` logging or the on-screen error detail.

**Startup migrations do not lose data or lock the user out.**
- Tests: `test_sqlite_migration.py`, `test_favorites_migration.py`.
- Strength: **E**.

**The active playlist is restored after a restart.**
- Tests: `test_restart_restore.py`, `test_main_window_wiring.py`.
- Strength: **E** for the identity path, **W** for the legacy path.
- The legacy path is broken, and the tests that cover it use a fake (F2).

**Playlist loading (file / URL / Xtream) is bounded, retried and validated.**
- Tests: `test_download_limits.py`, `test_playlist_url_and_query.py`, `test_xtream_validation.py`, `test_probe_cancellation.py`.
- Strength: **E**.

**The saved library keeps user data: names, Xtream password on edit, entries.**
- Tests: playlist-manager tests in `test_models_and_services.py`, `test_playlist_switching.py`.
- Strength: **W**.
- MUT-E survived. The `_edit_playlist` flow and blank-password-on-edit have no test.

### High

**EPG cache lifecycle: a load replaces the cache, and a cancelled load writes nothing.**
- Tests: none at that level.
- Strength: **W**. MUT-A and MUT-B survived.

**The Xtream provider guide auto-loads per provider and freshness is per identity.**
- Tests: none.
- Strength: **W**. MUT-C survived.

**Stale background results are suppressed.**
- Tests: `test_async_controllers.py`, parametrized over both controllers.
- Strength: **E**.

**Player reconnect state machine: bounded, resettable, stoppable.**
- Tests: `test_models_and_services.py:528`, `test_logging.py:93`.
- Strength: **W**. MUT-G and MUT-I survived.

**Playback is refused when no embedded surface exists.**
- Tests: `test_video_embedding.py`.
- Strength: **E**.

**Channel identity `(url, playlist_path)` is used for favourites and history.**
- Tests: `test_history_repository.py`, `test_favorites_migration.py`.
- Strength: **E**.
- `highlight_channel` is tested only with distinct URLs.

### Medium

**Search and sort.**
- Tests: `test_playlist_url_and_query.py`.
- Strength: **E** for sort.
- **W** for group search: README says "Search channels or groups", and MUT-D survived.

**EPG now/next lookup and the restart DB-cache path.**
- Tests: `test_epg_now_next.py`, `test_epg_and_settings_robustness.py`.
- Strength: **E**.

**Layer boundaries.**
- Tests: `test_layer_boundaries.py`.
- Strength: **E** (import level).

**Layout, theme and rendering.**
- Tests: `test_ui_layout.py`, `test_ui_theme.py`, `test_channel_list_view_updates.py`.
- Strength: **U**. They are brittle: thresholds depend on fonts, and pixels are checked at fixed coordinates.

**Notification queueing.**
- Tests: `test_models_and_services.py:739`.
- Strength: **W** (misleading, F8).

### Low

**Parser tolerance for malformed timestamps.**
- Tests: `test_backend_performance_paths.py`.
- These are characterization tests. They lock in permissive parsing, and whether that is intended is ambiguous.

**Helpers used only by tests.**
- Tests: several (F10). They protect nothing in production.

**Imbalance:** the critical and high **stateful** rows (library, EPG lifecycle, provider guide, reconnect) are the weak ones. Pure, low-risk parsing and helper paths get proportionally more tests.

---

## 4. Strongest and weakest areas

### Strongest

- **`test_download_limits.py`.**
  - It exercises byte budgets, deadlines, and 4xx vs 408/429/5xx retry classification.
  - It checks that limit errors are not retried, and the backoff timing.
  - It uses real `read_bounded` and scripted responses. It was the only test to kill the control mutant.
- **`test_credential_redaction.py`.** Its assertions check what is actually logged (caplog) and the error text, using credentialed URLs, including passwords in the path.
- **`test_xtream_validation.py`.**
  - It isolates each auth decision: banned/disabled status with auth set, and unauthenticated with Active status.
  - It is table-driven, and every row fails for a distinct regression.
- **`test_sqlite_migration.py`.**
  - Real legacy schemas.
  - Failure injection in the middle of a migration, with rollback and retry on the next start.
  - File-mode checks.
- **`test_async_controllers.py`.** One parametrized contract for both controllers: a stale result after a newer request is dropped, and cancellation is cooperative.
- **`test_restart_restore.py` (real-stack half, lines 61–184).** A true process-lifetime round trip on one SQLite file. It includes "a deleted Xtream entry does not fall back to the previous file."
- **`test_video_embedding.py`.**
  - Refusing to play without a bound surface is tested both with a mocked bind and with the real `bind_video_output` under offscreen Qt.
  - It asserts that no `media_new`/`set_media`/`play` call happens and the timer stays inactive.
- **`test_channel_list_view_updates.py` and `test_searchable_combo_box.py`.** Real `QTest` input, bounded event loops, and behavioural scroll and selection assertions.

### Weakest

- **EPG persistence lifecycle.** No test loads two guides in a row or cancels between parse and save. (MUT-A, MUT-B)
- **Player reconnect and stop semantics.**
  - The cap test stubs `play`, so the real `is_retry` path never runs.
  - No test arms the reconnect timer and then calls `stop()`. (MUT-G, MUT-I)
- **Exception logging in `PlayerWidget.play()`.** No test makes VLC raise. (MUT-H)
- **Main-window state decisions.**
  - Guide freshness per provider (MUT-C) and library naming (MUT-E) live in `MainWindow`, with no test.
  - The playlist-manager edit and save flow (`_open_playlist_manager` → `_save_playlists_from_dialog`, `PlaylistManagerDialog._edit_playlist`) has no test.
- **Legacy restore.** Fake-based tests pass for behaviour the real stack does not have (F2).

---

## 5. Mutation results

**Method:**
- `rsync` copy of the repo into the session scratchpad, excluding `.venv`, `.git` and caches. It was verified to import its own modules.
- Each mutant is an exact, single-occurrence string replacement, followed by a full-suite run.
- After each run the file is restored from the original and checked byte-for-byte.
- Proof of cleanliness: `diff -rq` between the copy and the repo, excluding caches and logs, showed only `repomix-output.xml`, which was excluded from the copy. `git status` is unchanged from the start of the audit.

### Survived

**MUT-A: `core/services/epg_service.py:57`**
- Mutation: removed the `_ensure_not_cancelled(...)` call that runs before `repository.save_all(...)`.
- Simulated regression: a guide load cancelled or superseded after parsing still overwrites the SQLite guide cache.
- Result: **SURVIVED** (491 passed).

**MUT-B: `infra/db/epg_repository.py:39`**
- Mutation: dropped `DELETE FROM epg_data` in `save_all`.
- Simulated regression: loading guide B keeps guide A's rows, so now/next mixes two providers. The mix persists across restarts.
- Result: **SURVIVED**.

**MUT-C: `ui/windows/main_window.py:806-809`**
- Mutation: the freshness skip no longer compares `last_epg_xtream_identity` with the active provider.
- Simulated regression: switching to provider B reuses provider A's "fresh" guide and never loads B's guide.
- Result: **SURVIVED**.

**MUT-D: `core/services/playlist_service.py:142`**
- Mutation: search matches only `channel.name`, not `channel.group`.
- Simulated regression: the documented "Search channels or groups" stops matching groups.
- Result: **SURVIVED**.

**MUT-E: `ui/windows/main_window.py:423-424`**
- Mutation: `_persist_playlist_state` ignores `existing_reference.name`.
- Simulated regression: every reload renames the user's saved entry to "URL Playlist" or to the file name.
- Result: **SURVIVED**.

**MUT-F (planned control): `ui/controllers/epg_controller.py:88`**
- Mutation: `_last_loaded_source = source`, instead of `xtream_identity or source`.
- Simulated regression: the in-memory "last source" holds the credentialed Xtream guide URL.
- Result: **SURVIVED**.
- Assessment: **near-equivalent.** In the Xtream branch, `_on_epg_loaded` (`main_window.py:475-483`) persists `epg_url=""` plus the identity, and never reads `last_loaded_source`. So the value is never persisted or displayed. Low impact.

**MUT-G: `ui/widgets/player_widget.py:254-255`**
- Mutation: `reconnect_attempts = 0` runs unconditionally, instead of only when `not is_retry`.
- Simulated regression: every timer-driven retry resets the counter, so a dead stream is retried forever.
- Result: **SURVIVED**.

**MUT-H: `ui/widgets/player_widget.py:275`**
- Mutation: the log line uses `exc` instead of `type(exc).__name__`.
- Simulated regression: the VLC exception text, which can echo the stream URL with the Xtream password in its path, is written to `iptv_player.log`.
- Result: **SURVIVED**.

**MUT-I: `ui/widgets/player_widget.py:285`**
- Mutation: `stop()` no longer calls `reconnect_timer.stop()`.
- Simulated regression: pressing Stop during a pending reconnect restarts the stream a few seconds later.
- Result: **SURVIVED**.

### Killed

**MUT-J (positive control): `core/services/playlist_service.py:414`**
- Mutation: default `max_retries: int = 3` changed to `2`.
- Simulated regression: one fewer download attempt.
- Result: **KILLED** (1 failed, 490 passed).
- Killing test: `test_download_limits.py::test_playlist_retry_backoff_is_exponential_and_skips_final_attempt`.
- Notes:
  - The production call site passes `max_retries=3` explicitly (`playlist_service.py:304`). So the default is reached only through tests that call the private `_download_with_retries`.
  - `test_download_failure_attempts_three_times_then_raises` goes through the public path. It would catch a change at the call site, but not this mutant.
  - The duplicated literal `3` is a minor smell.

---

## 6. Prioritized findings

**Priority scale**
- **P1:** protects critical or high behaviour now proven unprotected, or hides a defect.
- **P2:** high or medium behaviour with a proven gap.
- **P3:** quality, brittleness or runtime.
- **P4:** cleanup.

**Effort scale:** XS < 30 min, S ≈ 1–2 h, M ≈ half a day.

### F1: Missing test. The EPG cache lifecycle is unprotected. **P1 · S**
- **Production path:** `core/services/epg_service.py:41-63` (cancellation checks around `save_all`), `infra/db/epg_repository.py:36-39`.
- **Test path:** none.
  - `tests/test_epg_and_settings_robustness.py` already builds a real `EPGService(EPGRepository(SQLiteConnection(tmp_path)))`, but only checks a single load.
  - The `_FailingEPGRepository` tests check only error wrapping.
- **Weakness:** no test runs two loads in sequence, or a cancellation after the parse.
- **Escaping regression:**
  - `docs/archive/PERFORMANCE_AUDIT.md` measures EPG parse at about 9.5 s and `save_all` at about 1.4 s, which makes this path a refactor target.
  - A switch to incremental `INSERT OR REPLACE` without the `DELETE` would leave stale channels from the previous provider.
  - Dropping the pre-save cancellation check would let a superseded load overwrite the cache.
  - Both corrupt data silently, and the corruption survives restarts (MUT-A, MUT-B).
- **Recommended level:** service + real repository integration, in `test_epg_and_settings_robustness.py`.
- **Recommended scenarios:**
  1. Load guide A (channel `a`), then guide B (channel `b` only). The repository returns no programme for `a`, and B's programme for `b`.
  2. Load guide A. Then load guide B with a `cancel_callback` that becomes true after parsing. Expect `CancelledError`, and the DB still returns A's programme.

### F2: Misleading test that hides a confirmed defect: legacy active-playlist restore. **P1 · S–M**

> **Resolved 2026-10-20 (after the audit):** legacy support was dropped.
> - The legacy fallback was removed from `MainController.start`; restore now uses the identity only.
> - The 13 dict-fake tests were deleted.
> - `test_main_controller_does_nothing_without_saved_state` was rewritten on the real stack as `test_restart_without_saved_state_loads_nothing`.
> - The full suite has 478 passing tests.
> - The playlist legacy keys were removed afterwards:
>   - `last_playlist` and `last_playlist_is_url` are no longer seeded, written or read.
>   - `PlaylistService.build_legacy_reference` was deleted.
>   - Existing databases keep the old rows, which nothing reads.
>   - The EPG mirror keys (`last_epg_file`, `epg_url`) remain.
- **Production path:**
  - `ui/controllers/main_controller.py:6-24` (legacy fallback reading `last_playlist`, `last_playlist_is_url`)
  - `core/services/settings_service.py:101-104` (`get_setting` returns the default for keys that are not dataclass fields)
  - `infra/db/sqlite_connection.py:160-161` and `:168` (`INSERT OR IGNORE` seeds `last_playlist_path=''`, and `last_playlist_source_type='file'`)
- **Test path:** `tests/test_restart_restore.py:200-251`
  - `_DictSettingsController`
  - `test_main_controller_legacy_fallback_matrix` (12 rows)
  - `test_main_controller_legacy_fallback_uses_old_last_playlist_key`
- **Weakness:** the fake returns any key it is given. The real `SettingsController` never exposes `last_playlist_is_url` or `last_playlist`, so the tested branch cannot be reached in production.
- **Observed through the real stack** (probe on seeded legacy SQLite files):
  1. A DB with only `last_playlist=<URL>` and `last_playlist_is_url=true`. Startup rewrites `last_playlist` to `''`, and nothing loads.
  2. A DB with `last_playlist_path=<URL>`, `last_playlist_is_url=true` and no source type. The playlist loads as a **file** and fails with `ValidationError: Playlist file not found: <cwd>/https:/example.com/list.m3u`.
- **Ambiguity, not decided here:** it is a product call whether databases from before `source_type`/identity still need support. Current builds always write `last_playlist_identity`.
  - If they do: route legacy keys through `SettingsService`, for example by mapping them in `_load_settings`.
  - If they don't: delete the legacy branch together with the 13 tests.
- **Recommended level:** integration through the real `SettingsService`/`SettingsController` on a seeded legacy SQLite file. Never through a dict fake.
- **Scenario:** seed each legacy shape, then run `MainController.start()`. Assert the recorded `(source, is_url)`, or assert that nothing is loaded if support is dropped.

### F3: Missing test. Xtream guide freshness is not checked per provider. **P1 · S**
- **Production path:** `ui/windows/main_window.py:797-811` (`_auto_load_xtream_epg`, `_epg_cache_is_fresh`).
- **Test path:** none.
- **Escaping regression:** MUT-C. Users with two providers see provider A's schedule on provider B's channels until the cache ages out.
- **Recommended level:** extract the decision into a small pure function or a controller method `should_load_provider_guide(settings, identity, now)`, and unit-test it. Otherwise, use a `_build_window` wiring test.
- **Scenario:** `last_epg_xtream_identity=A` with a fresh `last_epg_loaded_at`.
  - Activating B triggers a load.
  - Activating A does not.
  - A stale timestamp for A triggers a load.
  - A manual `last_epg_path`/`epg_url` suppresses the auto-load.

### F4: Missing test. The player reconnect state machine is only tested through a stub. **P1 · S**
- **Production path:** `ui/widgets/player_widget.py:244-256` (`play`, `is_retry`), `:278-287` (`stop`), `:390-410` (`_handle_playback_error`).
- **Test path:**
  - `tests/test_models_and_services.py:528` runs the real handler on a hand-built `SimpleNamespace`, with `play` replaced by a lambda.
  - `tests/test_logging.py:93` calls `_handle_playback_error` directly.
- **Weakness:**
  - The real `play(is_retry=True)` never runs.
  - No test arms the timer and then calls `stop()`.
  - The production cap (`max_reconnect_attempts = 5`, `:169`) and the 30 s backoff ceiling (`:395`) are never pinned.
- **Escaping regressions:** MUT-G (infinite reconnect) and MUT-I (Stop does not cancel a pending reconnect).
- **Recommended level:** widget test with a real `PlayerWidget` and a fake VLC instance. The fixture already exists at `tests/test_logging.py:33`. Fire `reconnect_timer.timeout` by hand, with no real waiting.
- **Scenarios:**
  - Error, then timeout, then error, and so on. After the cap, the state is "error", the timer is inactive, and no further `media_new` calls happen.
  - Error, so the timer is armed, then `stop()`. The timer is inactive and `media_new` is not called again.
- **Follow-on:** retire the `SimpleNamespace` version (Brittle).

### F5: Missing test. Credential leak through the `play()` exception path. **P1 · XS**
- **Production path:** `ui/widgets/player_widget.py:273-276`.
- **Related paths, not mutated:**
  - `_handle_playback_error` copies the raw `error_msg` into the placeholder and the state detail (`:390`, `:410`).
  - `MainWindow.show_notification` logs messages raw (`main_window.py:863-869`).
- **Test path:** `tests/test_logging.py:93,274,316` cover other paths. Nothing makes `media_new`/`set_media`/`play` raise.
- **Escaping regression:** MUT-H. Making the log message "more helpful" writes the Xtream password, carried in the URL path, to `iptv_player.log`. `RedactingFormatter` does not mask path passwords.
- **Recommended level:** widget test with the existing fake-instance fixture.
- **Scenario:**
  - `media_new` raises `RuntimeError(url)`, where `url = http://host/live/alice/SECRET/1.ts`.
  - Assert `SECRET` is absent from caplog at DEBUG, from `placeholder.text()`, and from the state detail.

### F6: Missing test. Saved-library user data: names, and the Xtream password on edit. **P2 · S**
- **Production path:**
  - `ui/windows/main_window.py:416-431`: library naming lives in the window.
  - `ui/dialogs/xtream_source_dialog.py:146-149`: a blank password field keeps the saved password.
  - `PlaylistManagerDialog._edit_playlist`.
  - `infra/db/playlist_repository.py:16-20`: `save_playlists` does DELETE plus a raw INSERT, with no blank-password guard.
- **Test path:** none for naming or edit.
- **Weakness:**
  - MUT-E survived.
  - The only barrier against blanking a saved password is `PlaylistService._normalize_reference`, which rejects empty passwords. That validator is well tested (`test_xtream_validation.py`).
  - The dialog's keep-the-saved-password fallback is not tested at all. Breaking it would turn every edit into "password is required": a loud failure, not data loss.
  - The empty-password `CASE` in `upsert_playlist` (`playlist_repository.py:85-88`) cannot be reached through the service.
- **Recommended level:**
  - Move the naming rule into `PlaylistService`, for example `save_loaded_reference`, and unit-test it there.
  - Test `XtreamSourceDialog(reference).to_reference()` with a blank field at widget level.
- **Scenarios:**
  - Save "My TV", reload the same identity, and the name is still "My TV".
  - Open edit on a saved Xtream entry, change only the username, and the saved password is kept.

### F7: Missing test. Search by group. **P2 · XS**
- **Production path:** `core/services/playlist_service.py:142`.
- **Test path:** `tests/test_playlist_url_and_query.py` covers sort only.
- **Escaping regression:** MUT-D. Group search, a documented feature, silently disappears.
- **Recommended level:** unit test on `search_channels`.
- **Scenario:** searching `"news"` returns channels in group "News" whose names do not contain "news". Searching is case-insensitive.

### F8: Misleading test. The notification queue test checks none of the three behaviours in its name. **P3 · XS**
- **Test path:** `tests/test_models_and_services.py:739-753`.
- **Production path:** `ui/widgets/notification.py:39-56`.
- **Weakness:**
  - The parent is never shown, so `isVisible()` is false and messages are never queued (line 53).
  - The x position changes only because "Second" is wider than "First".
  - `_advance_queue()` changes nothing.
  - Found by the delegated UI review with a probe, and confirmed against the code.
- **Escaping regression:** removing the queue, or the reposition-on-resize `eventFilter`.
- **Scenario:** call `parent.show()`, then:
  - assert `len(notification._queue) == 1` after the second message (or check that the first text is still shown);
  - resize with an unchanged text and check that x moves;
  - fire the timer and check the second message appears.

### F9: Lenient exception assertions and a stale comment. **P3 · XS**
- **`tests/test_playlist_url_and_query.py:99-105`.**
  - It accepts `(CancelledError, ParsingError)`.
  - Its comment says the service "re-wraps the cancellation as ParsingError". That is no longer true: `_load_from_url` re-raises `CancelledError`.
  - Re-wrapping again would show an error toast when the user cancels. Only `test_probe_cancellation.py` would catch that, and not at this spot.
  - Fix: assert `CancelledError` exactly, and correct the comment.
- **`tests/test_credential_redaction.py:341`.** It accepts `(NetworkError, ValidationError)` for a bad port. Pin the actual contract.

### F10: Invalid or obsolete tests that protect production-dead code. **P3 · S**

Callers were checked across the whole repo with `rg`.

**Dead in production, but protected by tests:**

| Dead code | Tests |
|---|---|
| `PlaylistReference.from_settings_value` | `test_epg_and_settings_robustness.py:52-75` (3 tests) |
| `PlaylistReference.to_settings_value` (also documented as an invariant in `AGENTS.md`) | `test_models_and_services.py:945` |
| `EPGRepository.save_program` | `test_models_and_services.py:305`, and `test_epg_now_next.py:163` (as a fixture helper) |
| `XtreamClient._build_live_stream_url` | `test_models_and_services.py:1029`, and `test_backend_performance_paths.py:264` (as the oracle) |

**Dead with no callers at all, tests included:**
- `HistoryService.get_last_played_at` (`core/services/history_service.py:18`), and `HistoryRepository.get_last_played_at` (`infra/db/history_repository.py:86`), which is reached only through that dead service method
- `PlaylistService.build_legacy_reference` (`core/services/playlist_service.py:254`)
- `Program.duration_minutes` (`core/models.py:355`)
- `Playlist._name_index` (`core/models.py:299`): written and cleared, never read

- **Weakness:**
  - These tests read as protection but guard nothing that ships.
  - `_build_live_stream_url` is especially misleading. Production builds stream URLs inline in `fetch_live_channels`, so a regression there passes the helper's test. `test_backend_performance_paths.py:264` even uses the helper as the oracle.
- **Recommendation:**
  - Delete the dead code together with its tests. For the URL helper, an alternative is to route production through `_build_live_stream_url` and test the public `fetch_live_channels`.
  - Update `AGENTS.md` if `to_settings_value` goes.
  - The second group is not a test problem; it is listed so cleanup can be done in one pass.

### F11: Brittle fakes and duplicated setup. **P3 · S–M**
- **`test_models_and_services.py:528`: retry test on a `SimpleNamespace` player.** It breaks whenever the handler touches a new attribute, and it cannot see real `play()`. Replace it with the F4 fixture.
- **`_fake_right_panel` tests (`:580-627`).**
  - Their reason no longer holds: `test_ui_layout` builds real `RightPanel`s under `no_vlc`.
  - Real coverage exists at `test_ui_layout.py:424-435`. These tests are **Redundant**.
  - They also miss that `right_panel.py:373` keeps the old detail text when a state with an empty detail arrives. (Reported by the delegated review; not re-verified.)
- **`_DummyPlaylistRepository`** is a hand-written repository fake, while real SQLite on `tmp_path` is cheap. Prefer the real repository.
- **Duplicate fakes.** A fake `requests` response class (`_Response` and variants) is redefined in about 6 files. Extract one builder into `conftest.py` or a `tests/_http.py` helper.
- **`test_main_window_wiring.py::_build_window` duplicates `app.main.create_window`.** Wiring drift in `app/main.py` would pass. Have the test call `create_window` with injected paths, or add a single smoke test that does.
- **`test_ui_layout.py:468-588` (cross-source pending restore).** `_finish_render_of` re-implements part of `_on_playlist_loaded`, so it can drift silently. Drive the tests through the real handler. (Reported by the delegated review.)

### F12: Redundant or weak duplicates. **P4 · XS**
- **`test_models_and_services.py`, `test_xtream_client_auth_failure`.** It sets `auth=0` **and** `status=Disabled`, so it cannot tell the two checks apart. `test_xtream_validation.py` covers each separately. Delete it.
- **`test_playlist_service_handles_download_failure`.** It calls the private `_download_with_retries` and asserts only `NetworkError`. It is subsumed by `test_playlist_url_and_query.py:110-128`. Delete it.
- **Third test in `test_playlist_switching.py`.** It largely repeats the first two.

### F13: Characterization tests that lock in permissive parsing. **P4 · ambiguity**
- **Test path:** `tests/test_backend_performance_paths.py`.
- **What it locks in:** it accepts `"20240115103000garbage"` and the 13-digit `"2024011510300"` as valid XMLTV timestamps.
- **Unclear:** whether this tolerance is intended or an accident of the fast path.
- **Recommendation:** decide, then either document the tolerance in the test name or tighten the parser.

### F14: Slow tests caused by test-isolation leaks. **P3 · XS–S**
- **Test path:** `tests/test_ui_layout.py:628`, `test_playlist_manager_buttons_do_not_overlap[light|dark]`.
- **Cost:** 1.75 s and 1.73 s, about 53 % of the 6.6 s suite. Run alone it takes about 0.06 s.
- **Cause** (delegated review):
  - `qapp.setStyleSheet(...)` re-polishes every live widget, and so does the reset in `finally`.
  - About 2,085 widgets are still alive at that point, leaked by earlier tests that `close()` without `deleteLater()`, or never close (e.g. `LeftPanel()` at `:121`, `RightPanel` tests, the `_manager_with_playlist` dialogs).
- **Fix:**
  - (a) Use `dialog.setStyleSheet(...)`, as the `RightPanel` tests do. This saves about 3.4 s.
  - (b) Add a widget-cleanup fixture (close + `deleteLater` + `processEvents`). Any test that touches global Qt state currently depends on which tests ran before it.

### F15: Tests that lock in questionable behaviour. **P4**
- **`test_logging.py:255`.** It asserts `toggle_mute() is True` when VLC is unavailable, so the UI reports "muted" when nothing was muted. Decide on the contract.
- **`test_main_window_wiring.py`: "no password in settings".** This holds only because no channel is played. `_play_channel` stores `last_channel_url=channel.url` (`main_window.py:560`), and for Xtream that URL contains the password.
  - The password is already stored in the local `playlists` table, so this is not a new exposure.
  - But the test's claim is broader than what it checks. Either play an Xtream channel in the test and decide whether `last_channel_url` may hold credentials, or narrow the test name.

### Remaining concerns (not mutated)
- **Overlapping EPG loads.** The cache race recorded in the earlier audit is still open. This audit did not see a test for it.
- **Untested UI paths** (delegated review):
  - `MainWindow.keyPressEvent`; Space ignores modifiers
  - favourite toggle → list badge refresh
  - `_on_copy_stream_url`
  - the positive path of `retry_now`
  - settings persistence in `closeEvent`
  - the bind-exception fallback in `player_widget.py:215-218`
  - non-Linux branches of `vlc_backend.py`
- **The virtualization rule** (`QListView` + model, no row widgets) is guarded only indirectly. `…_without_row_widgets` (`test_models_and_services.py:701`) asserts neither `indexWidget` nor the view type.

---

## 7. Highest-return improvements

| # | Improvement | Kills | Effort |
|---|---|---|---|
| 1 | Two EPG lifecycle scenarios on the existing real-repository harness (F1) | MUT-A, MUT-B | S |
| 2 | Real `PlayerWidget` reconnect, stop and exception tests on the existing fake-instance fixture (F4, F5) | MUT-G, MUT-H, MUT-I | S |
| 3 | Settle the legacy-restore product question. Then replace the dict-fake matrix with a real-stack seeded-DB test, or delete branch and tests (F2). | Unmasks a defect | S–M |
| 4 | Extract the provider-guide freshness decision and table-test it (F3) | MUT-C | S |
| 5 | One group-search row (F7) | MUT-D | XS |
| 6 | Move library naming into `PlaylistService` and test that the name is preserved (F6) | MUT-E | S |
| 7 | Scope the stylesheet in the overlap test, and add a widget-cleanup fixture (F14) | About 3.4 s (≈ 50 % of runtime) and order-dependence | XS–S |
| 8 | Delete dead code with its tests, and remove the redundant duplicates (F10, F12) | Removes false confidence | S |

Items 1 and 2 together kill 5 of the 8 realistic survivors, using fixtures that already exist.

---

## 8. Single most dangerous missing test

> **The EPG cache lifecycle (F1): a second guide load must *replace* the cached guide, and a load cancelled after parsing must leave the previous cache intact.**

**Why this one:**
- It is the only gap where a plausible refactor causes **silent, persistent data corruption.**
  - A mixed or stale guide is written to SQLite and served again after every restart.
  - Users see it as wrong now/next information, with no error.
- The code is a likely refactor target. EPG parse and `save_all` are measured hotspots in `docs/archive/PERFORMANCE_AUDIT.md` (§2), and "streaming save" or "upsert instead of delete + insert" are natural optimizations.
- Two independent mutations of it (MUT-A, MUT-B) survived the entire suite.
- The real-repository harness already exists in `tests/test_epg_and_settings_robustness.py`, so the test costs minutes.

**Runner-up:** F5, the credential leak via `play()` exceptions. It has higher impact per occurrence, but it requires editing a line that already carries an explanatory comment.

---

## 9. Most misleading existing test

> **`tests/test_restart_restore.py::test_main_controller_legacy_fallback_matrix`** (12 parametrized rows), together with `test_main_controller_legacy_fallback_uses_old_last_playlist_key`.
>
> Both were deleted with the legacy branch on 2026-10-20 (see F2).

**Why it misleads:**
- The module docstring says it "Kills … M2 (legacy `is_url` flag inverted)", and the 12-row truth table looks exhaustive.
- It drives `MainController` with `_DictSettingsController`. That fake returns `last_playlist_is_url` and `last_playlist`, which the real `SettingsController` never returns. `SettingsService.get_setting` only returns `Settings` dataclass fields; everything else gets the default.
- Through the real stack, both legacy shapes fail (F2):
  - one restores nothing
  - the other treats a URL as a missing local file
- So the suite reports 13 green tests for a feature that does not work. The previous audit's "M2 killed" rests on these tests.

**Runner-up:** `test_notification_widget_queues_messages_and_repositions` (F8). None of the three behaviours in its name is exercised. Its behaviour is low-risk, though.

---

## 10. Recommended testing policy going forward

1. **Mutation-check every bug fix.** Before merging a fix, revert the production change locally and confirm the new test fails. This audit shows the suite's main failure mode: tests that pass whether or not the behaviour exists.
2. **No fake may be more capable than the real collaborator.**
   - Prefer the real service and repository on `tmp_path` SQLite; it is cheap here.
   - If a fake is needed, keep it to the real class's public surface. A dict-backed settings fake must not answer keys `SettingsService` hides.
3. **Stateful workflows need sequence tests.** Cover them with "do A, then B, then restart" scenarios through the real persistence layer, not single-call tests:
   - EPG cache
   - active-playlist restore
   - saved library
   - player reconnect
4. **Keep domain decisions out of windows.** Logic such as library naming and guide freshness belongs in services or controllers, where it can be unit-tested without building `MainWindow`.
5. **Security assertions follow every sink.**
   - Any path that can carry a stream URL (logs, notifications, placeholder or state text, persisted settings) gets a test using a URL with the password **in the path**.
   - `core/redaction.py` does not mask path passwords.
6. **Test the player through the real `PlayerWidget` with a fake VLC instance.** Never stub the method under test (`play`) when testing its state machine. Drive timers by emitting `timeout`, not by sleeping.
7. **Assert exact exception types.** Use a tuple only when both types are part of the contract, and keep comments in sync with production.
8. **Delete dead code together with its tests.** Do not test private helpers that production does not call.
9. **Keep Qt tests hermetic.**
   - No app-wide `setStyleSheet` in tests.
   - Created widgets are closed and `deleteLater`'d by a fixture.
   - Prefer behavioural geometry checks (no overlap, text not truncated) over fixed pixel coordinates and font-dependent thresholds.
10. **Budget:** keep the full suite under about 10 s locally. Investigate any test over 0.5 s.
11. **Coverage is not a target.** Use it only to find unexecuted critical branches, then write a behavioural test for them.

---

## 11. Verification status and working tree

| Check | Status |
|---|---|
| Full pytest, Python 3.14.8 | **PASS**: 491 passed in 6.62 s. No failures existed before the audit. |
| ruff check / ruff format --check | **PASS** / **PASS** |
| mypy ratchet | **PASS**: 75 errors, which is the recorded maximum. They existed before the audit. |
| pytest / mypy on Python 3.12 (CI matrix) | **NOT_RUN**: not installed locally |
| GUI run, real libvlc playback | **NOT_RUN**: outside audit scope, and would touch `~/.simple_iptv/` and the network |
| No mutations remaining | **PASS**. Mutations ran only in a scratch copy, each was restored and checked byte-identical, and `diff -rq` copy vs repo shows no source differences. |
| Working tree | **PASS**. `git status` equals the pre-audit snapshot plus `?? test_audit.md`. |

The changes to `AGENTS.md`, `README.md`, `docs/*.md` and `docs/archive/phase3.md` existed before this audit and were not touched.
