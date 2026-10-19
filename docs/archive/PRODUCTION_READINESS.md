# Production Readiness Review: Simple IPTV Player

Review date: 2026-10-18. Branch `v2`, HEAD `d7aeaa7`, clean tree.
Mode: REVIEW (read-only; no application code changed). Focus: GENERAL. Depth: DEEP.
Run state: `.claude/orchestration/runs/20261018T170502Z-production-readiness-review/state.md`.

## 1. Review scope and confidence

**Covered:** all of `app/`, `core/`, `infra/`, `ui/controllers/`, and the critical-path UI
(`main_window.py`, `player_widget.py`, `channel_list_view.py`, left/right panels, playlist
dialogs). Also CI workflows, dependency pins, docs and the test suite. Two read-only
scouts did the first pass. The orchestrator then checked every High/Medium claim against
the source or with a runtime probe.

**How each finding was verified** (tag on every finding):

- *probe*: reproduced by running the real code against temporary data (offscreen Qt,
  `tmp_path`-style SQLite in a scratch directory, no network).
- *source*: the orchestrator read the code path end to end.
- *scout*: reported with line evidence by a scout but not independently re-traced.
  Treat these as Likely.

**Not covered / limitations:**

- Native VLC playback was not exercised. Player findings come from source and an
  offscreen probe with VLC init mocked to fail.
- No real network, Xtream provider or real XMLTV feed was used.
- The local interpreter is Python 3.14.8, but CI uses 3.12. CI behaviour was not
  re-run this session.
- Fullscreen and window-close behaviour was reasoned from Qt semantics, not observed
  on a real display.
- Dependency advisories were not checked online (`pip-audit` needs network access).
- `ui/styles/themes.py`, `ui/widgets/epg_widget.py`, `notification.py` and `menu_bar.py`
  got only a light look.

Overall confidence: **high** for the parser, persistence and controller findings, and
**medium** for the playback and lifecycle findings.

## 2. Executive assessment

The codebase is in better shape than most hobby-scale desktop apps:

- Layering is real, and `tests/test_layer_boundaries.py` enforces it.
- Background loads are gated by task ID, so stale results are dropped.
- The channel list is properly virtualised.
- Service-level error paths redact URLs.
- 289 tests pass in about 3 s.

It is **not production-ready for arbitrary real-world sources**. The weak point is
input robustness: three probe-confirmed defects make whole loads fail on common
imperfect inputs.

- One duplicate programme in an XMLTV feed makes the entire EPG unusable.
- About half of non-UTF-8 (Latin-1/cp1252) playlists are rejected as "missing #EXTM3U".
- Unquoted M3U attributes are silently dropped.

Real IPTV feeds are messy, so users will hit these. Second-tier issues:

- One log path writes Xtream passwords to the log file.
- Credentials are stored in plaintext with world-readable default file modes.
- Downloads and decompression have no size cap.
- Shutdown does no teardown, and the app crashes on a play click when VLC is missing.
- A playlist-manager race can persist the wrong source.

None of this needs architectural change. Every fix is local. Severity is calibrated for
a local-first, single-user desktop app with no server or multi-tenant boundary, so
nothing is rated Critical.

## 3. Baseline facts

| Item | Value |
| --- | --- |
| Product | PyQt6 desktop IPTV player with M3U file/URL and Xtream sources, XMLTV EPG, native VLC via `python-vlc`, SQLite state in `~/.simple_iptv/database.db` |
| Entry point | `python -m app.main` (`app/main.py`) |
| Size | ~10k lines of Python. Largest files: `ui/windows/main_window.py` (899), `ui/styles/themes.py` (773), `core/services/playlist_service.py` (542) |
| Runtime deps | `requirements.txt`: PyQt6 6.8.0, python-vlc 3.0.21203, requests 2.32.3, urllib3 2.3.0, certifi 2024.12.14 (exact pins, no lockfile) |
| CI | `.github/workflows/lint.yml` (ruff check, ruff format --check, mypy non-blocking) and `tests.yml` (pytest, offscreen). Both run **only on `pull_request`**, with Python 3.12 |
| Local toolchain | `.venv/bin/python` 3.14.8 |

Baseline checks, run this session from the repo root at HEAD `d7aeaa7`:

| Command | Result |
| --- | --- |
| `.venv/bin/ruff check .` | PASS |
| `.venv/bin/ruff format --check .` | PASS (74 files) |
| `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q` | PASS (289 passed, 3.22 s) |
| `.venv/bin/mypy app core infra ui` | 75 errors in 11 files (non-blocking). It was 59 on 2026-10-17, so it is regressing unnoticed. Top offenders: `ui/widgets/channel_list_view.py` (32), `core/models.py` (23), `ui/dialogs/playlist_manager_dialog.py` (11), `ui/widgets/notification.py` (11) |

## 4. Top prioritized findings

| ID | Title | Sev | Conf | Verified by | When |
| --- | --- | --- | --- | --- | --- |
| F1 | Duplicate XMLTV programme aborts the entire EPG load | High | Confirmed | probe | Now |
| F2 | Non-UTF-8 playlists of even byte length are misdecoded as UTF-16 and rejected | High | Confirmed | probe | Now |
| F3 | Playlist-manager test result is written to the currently selected row | High | Confirmed | source | Now |
| F4 | Xtream password can reach the log file through the history error path | Medium | Confirmed | source | Now |
| F5 | Unquoted M3U attributes are silently dropped | Medium | Confirmed | source | Now |
| F6 | Play/retry crash with `AttributeError` when VLC is unavailable | Medium | Confirmed | probe | Now |
| F7 | No shutdown teardown, and fullscreen window can outlive main window | Medium | Confirmed (absence) / Likely (effect) | source | Soon |
| F8 | No size cap on downloads or gzip decompression, whole body held in memory | Medium | Confirmed | source | Soon |
| F9 | Plaintext Xtream passwords in a DB with default (world-readable) modes | Medium | Confirmed | source + `ls` | Soon |
| F10 | CI runs only on PRs, mypy errors growing, docs contradict CI | Medium | Confirmed | source + run | Soon |
| F11 | Runtime dependency pins date from late 2024 and are unaudited | Medium | Likely | manifest | Soon |
| F12 | Malformed XMLTV escapes as raw `ParseError`, not a domain error | Low | Confirmed | probe | With F1 |
| F13 | Legacy playlist-table migration is not atomic | Low | Likely | source | Later |
| F14 | Pending cross-source channel can auto-play after an unrelated load | Low | Likely | scout | Later |
| F15 | Logo cache unbounded, possible cache-key mismatch | Low | Likely | scout | Later |

Smaller items, Low and fix opportunistically:

- **Log file location:** the log is written relative to the current directory, and
  `configure_logging()` runs outside the startup `try` (`app/main.py:34,56,119`).
- **History grows forever:** `recent_channels` is never pruned
  (`infra/db/history_repository.py:15-30`).
- **Retries ignore 4xx and have no backoff** (`core/services/playlist_service.py:397-412`).
- **Playlist probe can't be cancelled**, even though it can run up to about 60 s
  (`playlist_manager_dialog.py:518`).
- **`_ensure_column` is dead code** (`infra/db/sqlite_connection.py:126-130`).
- **`batch_size` is unused** in `left_panel.set_channel_results` (`left_panel.py:316`).
- **Runtime connections skip setup:** they don't re-apply per-connection PRAGMAs or set
  a busy timeout (`sqlite_connection.py:26`). Impact is low because a 200k-programme
  EPG save takes 0.67 s (measured).

## 5. Architecture / codebase map

```text
app/main.py            logging, QApplication, excepthook, wiring (create_window), VLC-missing dialog
core/models.py         Channel (identity = (url, playlist_path)), Playlist, PlaylistReference, EPGChannel, Settings
core/services/         playlist_service (load/probe/download/query), epg_service (file/url -> parser -> repo),
                       settings/favorites/history services; redaction.py masks userinfo + query secrets only
infra/db/              SQLiteConnection: per-call connections, commit/rollback, embedded migrations;
                       repositories for playlists, settings, favorites, history, epg_data
infra/parsers/         m3u_parser (decode -> #EXTM3U check -> EXTINF/attrs), epg_parser (ElementTree, gzip)
infra/providers/       xtream_client (player_api, http->https fallback, stream URL build /live/u/p/id)
infra/playback/        vlc_backend (lazy libvlc init, instance, player)
ui/controllers/        BackgroundTask on QThreadPool; playlist/epg controllers gate results by task id
ui/windows/main_window MainWindow: signal hub, restore flow, settings persistence, closeEvent
ui/widgets/            player_widget (VLC state, reconnect, fullscreen window), channel_list_view (model/delegate),
                       left/right panels, logo provider (QNetworkAccessManager)
ui/dialogs/            playlist manager (add/edit/delete/test), Xtream source dialog
```

Critical paths:

- **Startup:** wire everything, `MainController.start()` restores the last source by
  identity (re-reading the Xtream password from the DB, covered by
  `tests/test_restart_restore.py:61`), then the last channel auto-plays.
- **Load source:** background task, service, parser or Xtream, `Playlist`, then the
  controller signal updates the left panel.
- **Load EPG:** background task, parse, `EPGRepository.save_all` (deletes everything,
  then inserts), and in-memory lookup per visible row.
- **Play:** `PlayerWidget.play(url)`, VLC, then the event handler, which uses queued
  Qt signals.

## 6. Detailed high-impact findings

### F1. Duplicate XMLTV programme aborts the entire EPG load
- **Severity:** High. **Dimension:** correctness / core domain. **Confidence:** Confirmed (probe).
- **Evidence:**
  - The table key is `PRIMARY KEY (channel_id, start_time)` (`infra/db/sqlite_connection.py:61`).
  - `EPGRepository.save_all` uses a plain `INSERT` (`infra/db/epg_repository.py:44`).
    `save_program` uses `INSERT OR REPLACE` (`:18`), so the two write paths disagree.
  - The parser appends programmes without deduplicating (`infra/parsers/epg_parser.py:~102`).
  - The probe fed an XMLTV file with two `<programme>` entries for the same channel and
    start into `EPGService.load_epg_from_path`. Result:
    `RepositoryError: Failed to persist EPG cache` (`UNIQUE constraint failed: epg_data.channel_id, epg_data.start_time`).
- **Problem:** one duplicate anywhere in a feed of tens of thousands of programmes
  rolls back the whole save, and the load fails.
- **Why it matters:** duplicate or overlapping entries are common in aggregated XMLTV
  feeds. The user gets no EPG at all, with an opaque persistence error.
- **If ignored:** EPG works with some providers and fails completely with others.
  That reads as random breakage.
- **Fix:** use `INSERT OR REPLACE` (last wins) in `save_all`, matching `save_program`.
  Also dedupe in `EPGParser` by `(channel, start)` so the in-memory and stored views
  agree, and switch the loop to `executemany`. Add a regression test with a duplicate
  programme.
- **Tradeoff:** "last wins" silently picks one of the conflicting entries. That is
  acceptable, and a parse warning can count the duplicates.

### F2. Non-UTF-8 playlists with an even byte length are misdecoded as UTF-16
- **Severity:** High. **Dimension:** correctness. **Confidence:** Confirmed (probe).
- **Evidence:**
  - `M3UParser._decode_playlist_content` tries `utf-8-sig`, `utf-8`, `utf-16`,
    `utf-16-le`, `utf-16-be`, then `iso-8859-1`, then `cp1252`
    (`infra/parsers/m3u_parser.py:143-156`).
  - BOM-less `utf-16` accepts almost any even-length byte string.
  - The probe used a Latin-1 playlist containing `Café TV`, padded to an even length.
    The decoded text did **not** start with `#EXTM3U`, so the header check rejects it.
- **Problem:** whether a Latin-1/cp1252 playlist loads depends on whether its byte
  count is odd or even.
- **Why it matters:** many European and legacy IPTV playlists are cp1252/Latin-1. About
  half of them fail with a misleading "Missing #EXTM3U header" error.
- **Fix:** only decode as UTF-16 when a UTF-16 BOM is present (`b"\xff\xfe"` or
  `b"\xfe\xff"`). Otherwise go `utf-8-sig`, then `utf-8`, then `cp1252`, then
  `iso-8859-1` (`iso-8859-1` never fails, so it must be last). Add tests for
  even-length and odd-length cp1252 files and for a UTF-16 file with a BOM.
- **Tradeoff:** BOM-less UTF-16 playlists stop being supported. They are vanishingly
  rare and were already unreliable.

### F3. Playlist-manager test result is written to the currently selected row
- **Severity:** High. **Dimension:** correctness (data integrity). **Confidence:** Confirmed (source).
- **Evidence:**
  - `_test_selected_playlist` captures `playlist` from the current item and starts a
    worker (`ui/dialogs/playlist_manager_dialog.py:509-525`).
  - `_on_test_succeeded` re-reads `self.playlist_list.currentItem()` and overwrites
    its `UserRole` data and text with the result (`:538-542`).
  - Only `test_button` is disabled during a test (`:523`). The list stays enabled.
  - On OK, `MainWindow` persists `dialog.get_playlists()` (`ui/windows/main_window.py:~716`).
- **Problem:** if the user selects another row while a test runs, which can take up to
  about 60 s with retries, the tested source's reference replaces the other row.
- **If ignored:** after OK, one source is silently duplicated or replaced by another.
  For Xtream sources that includes credentials.
- **Fix:** keep the `QListWidgetItem`, or the tested `source_identity`, when the test
  starts, and write the result to that item by matching identity. Add a dialog test that
  changes selection between start and succeed.
- **Tradeoff:** none.

### F4. Xtream password can reach the log file through the history error path
- **Severity:** Medium. **Dimension:** security / privacy. **Confidence:** Confirmed (source).
- **Evidence:**
  - `infra/db/history_repository.py:41` runs
    `logger.error("Failed to record channel history %s: %s", channel.url, exc)`.
  - Xtream channel URLs are `/live/<user>/<password>/<id>`
    (`infra/providers/xtream_client.py:301-306`).
  - `core/redaction.py` masks only userinfo and query keys, so it cannot redact path
    credentials. This breaks the AGENTS.md rule "Never log ... channel URLs".
- **Problem:** whenever a history write fails (a locked DB, a full disk), the
  plaintext Xtream password is written to `iptv_player.log`, a file users attach to bug
  reports.
- **Fix:**
  - Log `channel.name` (or `redact_identity` of the playlist path) instead of the URL.
  - Grep for any other `%s` that takes `channel.url` or `current_url`. The scouts found
    none in logging, but `ParseWarning.context` holds raw URL prefixes and must stay
    out of logs and UI.
  - Optionally add a `redact_stream_url()` that masks the `/live|movie|series/<u>/<p>/`
    segments, and use it defensively in `player_widget._mask_urls`.
- **Tradeoff:** a less specific log line.

### F5. Unquoted M3U attributes are silently dropped
- **Severity:** Medium. **Dimension:** correctness. **Confidence:** Confirmed (source).
- **Evidence:** `_ATTRIBUTE_RE = r'(\w[\w-]*)=(?:"([^"]*)"|\'([^\']*)\')'`
  (`infra/parsers/m3u_parser.py:21`) accepts only quoted values. `tvg-id=foo` yields no
  `epg_id`, and no warning is emitted.
- **Why it matters:** unquoted attributes do appear in real playlists. Losing `tvg-id`
  breaks EPG matching for those channels, and `group-title` and `tvg-logo` are lost
  too, all invisibly.
- **Fix:** add an unquoted alternative, `|([^\s,"']+)`, and a parser test. Do it in the
  same slice as F2.

### F6. Play/retry crash with `AttributeError` when VLC is unavailable
- **Severity:** Medium. **Dimension:** correctness / startup robustness. **Confidence:** Confirmed (probe).
- **Evidence:**
  - `PlayerWidget.__init__` returns early when VLC init fails
    (`ui/widgets/player_widget.py:127-128`).
  - That happens before `current_url`, `is_fullscreen`, `fullscreen_window`,
    `reconnect_timer` and `reconnect_attempts` are set (`:142-156`).
  - Probe with `VLCBackend.initialize` mocked to fail: `w.current_url` and
    `w.retry_now()` both raise `AttributeError`.
  - `MainWindow._on_play_button` reads `player_widget.current_url` when no channel is
    selected (`ui/windows/main_window.py:594`). `_on_copy_stream_url` reads it too (`:615`).
- **Problem:** the app explicitly supports running without VLC (`app/main.py` shows a
  warning and continues), but basic controls then raise errors. The excepthook shows an
  "Application Error" dialog.
- **Fix:** initialise all instance attributes before the early return. Add a test that
  builds `PlayerWidget` with init mocked to fail and calls `play`, `retry_now`,
  `toggle_fullscreen` and `stop`.

### F7. No shutdown teardown, and the fullscreen window can outlive the main window
- **Severity:** Medium. **Dimension:** lifecycle. **Confidence:** Confirmed for the
  absence (source), Likely for the effect.
- **Evidence:**
  - `MainWindow.closeEvent` only saves settings (`ui/windows/main_window.py:821-841`).
  - `rg "waitForDone|aboutToQuit|\.release\("` finds nothing in `app/`, `core/`,
    `infra/` or `ui/`.
  - `FullscreenPlayerWindow` is a parentless top-level window
    (`ui/widgets/player_widget.py:61`). Its `closeEvent` ignores the close (`:81-83`).
- **Problem:** closing while a stream plays does not stop VLC, cancel loads, or wait
  for the thread pool. Closing the main window while fullscreen leaves a top-level
  window open, so `quitOnLastWindowClosed` never fires.
- **If ignored:** audio can keep playing during teardown, the process can hang on exit,
  and libvlc can crash on exit (a common VLC symptom when the player is destroyed with
  live callbacks).
- **Fix:** in `closeEvent`, exit fullscreen, stop the player, cancel playlist, EPG and
  probe tasks, then `QThreadPool.globalInstance().waitForDone(2000)`. Add a
  `PlayerWidget.shutdown()` that stops the reconnect timer, stops and releases the player,
  and closes the fullscreen window. Add a test that calls `close()` on a wired window
  with a fake player.
- **Tradeoff:** exit can be delayed by up to the wait timeout while a blocking
  `requests` call finishes.

### F8. No size cap on downloads or gzip decompression
- **Severity:** Medium. **Dimension:** abuse resistance / performance. **Confidence:** Confirmed (source).
- **Evidence:**
  - `requests.get(url, timeout=20)` then `response.content`, with no `stream=True` and no
    limit (`core/services/playlist_service.py:399-401`). The EPG download path does the
    same (`core/services/epg_service.py:77-82`).
  - `gzip.open(...)` goes straight into `ET.parse` with no decompressed-size limit
    (`infra/parsers/epg_parser.py:56-58`).
  - Xtream `response.json()` is unbounded (`infra/providers/xtream_client.py:173-181,259`).
- **Problem:** a hostile or broken source, such as a gzip bomb, an endless response or
  a multi-GB feed, can exhaust memory. `timeout=20` is per read, so a slow-drip server
  can hold a worker indefinitely.
- **Fix:**
  - Stream downloads with a byte budget, for example 200 MB for playlists and 500 MB for
    EPG, and raise `NetworkError` when it is exceeded.
  - Wrap the gzip stream in a reader that counts decompressed bytes against a limit.
  - Consider a total wall-clock deadline per download.
- **Tradeoff:** limits must be generous enough for real large EPGs, and should be
  constants in one place.

### F9. Plaintext Xtream passwords in a DB with world-readable default modes
- **Severity:** Medium. **Dimension:** security. **Confidence:** Confirmed.
- **Evidence:**
  - The schema has `xtream_password TEXT NOT NULL` (`infra/db/sqlite_connection.py:176`).
  - `mkdir(parents=True, exist_ok=True)` uses no mode (`:20`), and there is no `chmod`
    anywhere in the repo.
  - On this machine `~/.simple_iptv` is `drwxr-xr-x` and `database.db` is `-rw-r--r--`
    (metadata only, contents not read).
- **Problem:** on multi-user systems other local accounts can read the credentials.
  WAL/SHM side files inherit the same permissions.
- **Fix:** create the directory with `0o700` and `chmod 0o600` the DB, `-wal` and `-shm`
  files at startup on POSIX. Fix the modes of existing installs too. Moving to the OS
  keyring is a larger change and is listed under "not yet".
- **Tradeoff:** none on POSIX. On Windows it is a no-op, and that is acceptable.

### F10. CI only on PRs, mypy regressing, docs contradict CI
- **Severity:** Medium. **Dimension:** developer experience / CI. **Confidence:** Confirmed.
- **Evidence:**
  - Both workflows use `on: [pull_request]`, so direct pushes to `main` or `v2` run nothing.
  - mypy went from 59 to 75 errors in a day, and it is `continue-on-error` (`lint.yml`).
  - `docs/architecture.md:123` says "no ... CI test job yet", and `docs/roadmap.md:8`
    says "add a pytest job". `tests.yml` already exists.
  - CI tests only 3.12, while local development is on 3.14.
- **Fix:**
  - Add `push: branches: [main]` to both workflows. This needs explicit approval
    (AGENTS.md protects `.github/`).
  - Make mypy a ratchet: fail if the error count rises above a recorded number.
  - Fix the two stale doc lines.
  - Optionally add 3.14 to the test matrix.

### F11. Runtime dependency pins date from late 2024 and are unaudited
- **Severity:** Medium. **Dimension:** dependencies / security. **Confidence:** Likely.
- **Evidence:** `requirements.txt` pins `requests==2.32.3`, `urllib3==2.3.0` and
  `certifi==2024.12.14`, about 22 months old. `certifi`'s version is the CA bundle
  date. There is no Dependabot or `pip-audit` in CI.
- **Problem:** `requests` and `urllib3` are the app's whole network attack surface, and
  advisories against those versions are likely. This was not verified online this session.
- **Fix:** run `pip-audit -r requirements.txt` (networked, needs approval). Bump
  `requests`, `urllib3`, `certifi`, `idna` and `charset-normalizer` to current patch
  releases, and add a scheduled Dependabot config. Check that PyQt6 6.8.0 wheels exist
  for every Python version CI targets.

### F12. Malformed XMLTV escapes as raw `ParseError`
- **Severity:** Low. **Dimension:** error handling. **Confidence:** Confirmed (probe).
- **Evidence:**
  - `ET.parse` is unguarded (`infra/parsers/epg_parser.py:56-60`).
  - `EPGService` only maps `ValueError` (`core/services/epg_service.py:44-52`).
  - The probe confirmed `issubclass(ET.ParseError, ValueError) is False`. A malformed
    file raised `xml.etree.ElementTree.ParseError` and was logged as "Unexpected EPG
    parser failure".
  - The worker's catch-all (`ui/controllers/background_tasks.py:42-44`) still shows
    `str(exc)`, so nothing crashes.
- **Fix:** catch `ET.ParseError` in `EPGParser` and re-raise it as `ValueError` with
  the line and column. Do this in the F1 slice.

### F13. Legacy playlist-table migration is not atomic
- **Severity:** Low. **Dimension:** persistence. **Confidence:** Likely (source).
- **Evidence:**
  - `executescript` commits the pending transaction and runs `ALTER TABLE ... RENAME` and
    `CREATE TABLE` outside it (`infra/db/sqlite_connection.py:214-236`).
  - The row-copy loop and `DROP TABLE playlists_legacy` (`:239-287`) then run in a new
    implicit transaction.
  - The column-set check (`:189-200`) treats the new empty table as already migrated.
- **Problem:** if the copy fails, the next start sees a fully shaped empty `playlists`
  table and skips the migration. The user's library is stranded in `playlists_legacy`.
  This only affects one-time upgrades from the legacy schema.
- **Fix:** run the whole migration with explicit `BEGIN` and `COMMIT`, using individual
  `execute` calls rather than `executescript`. Add a `PRAGMA user_version` for future
  migrations.

### F14 / F15 (scout-reported, Low)
- **F14:** `_pending_channel_url` is set on a cross-source click
  (`ui/windows/main_window.py:516-518`) but cleared only on render-complete
  (`:436-446`). After a failed load, a later unrelated load can auto-play that channel.
  Fix: clear it in `_on_error` and on any user-initiated load.
- **F15:** the logo provider (`ui/widgets/left_panel.py:49-90`) has no in-flight cap,
  no eviction and no timeout. Its cache is keyed by `reply.url().toString()`, which may
  differ from the requested string after normalisation, so a fetched logo may never
  replace the fallback. Fix: key by the requested string, and add an LRU bound and a
  transfer timeout.

## 7. Checked and not a problem (with evidence)

- **Large-playlist performance:** with 50k synthetic channels,
  `PlaylistService.query_channels` takes 6–10 ms (empty, broad and narrow queries), and
  `ChannelListView.set_channels` takes 2 ms. Now-playing lookups run only for visible
  rows (`left_panel.py:452-462`). Searching on the GUI thread is fine; do not move it
  off-thread.
- **EPG persistence speed:** `save_all` with 200k programmes (1000 channels × 200) takes
  0.67 s. SQLite lock contention is not a practical concern at this scale.
- **SQLite threading:** every operation opens its own connection with commit or
  rollback (`sqlite_connection.py:23-36`). There is no shared-connection hazard.
- **Stale results:** playlist and EPG controllers drop out-of-date results by task ID
  (`playlist_controller.py:194-219`, `epg_controller.py:93-117`), and tests cover it.
- **Xtream restart restore:** the password is re-read from the DB by identity
  (`main_controller.py:7-12`), covered by `tests/test_restart_restore.py:61`.
- **Reconnect:** bounded to 5 attempts with capped backoff (`player_widget.py:156,295-297`).
  VLC events reach Qt through queued signals.
- **Redaction:** service-level error messages and logs redact URLs
  (`playlist_service.py:311-318`, `epg_service.py:90-96`, `xtream_client.py:316-323`).
- **Temp files:** temporary download files are cleaned up.

## 8. Design choices to confirm (not defects)

- **Auto-play on start:** the last channel plays without user action
  (`main_window.py:446,529-534`).
- **Raw stream URL on screen:** Channel Info and Copy URL show the raw stream URL,
  including Xtream credentials (`main_window.py:615,642`). The player error placeholder
  shows unmasked `str(exc)` (`player_widget.py:292`). This is the user's own data on
  their own screen, so it is acceptable, but a masked display with an explicit copy
  action would be safer when the user screen-shares.
- **Xtream over HTTP:** credentials go over plain HTTP if the user typed `http://`.
  HTTPS is tried only after a connection error (`xtream_client.py:173,202-208`). This is
  the ecosystem norm; consider a one-time warning.
- **Single EPG cache:** loading an EPG wipes the previous source's cache
  (`epg_repository.py:38`). There is one EPG at a time, which is undocumented.

## 9. Prioritized roadmap

1. **Slice 1, input robustness** (F1, F2, F5, F12). This touches `infra/parsers/`,
   `infra/db/epg_repository.py` and new tests only. All four are confirmed, local to the
   parsers, and covered by this review's probes, which can become the tests.
2. **Slice 2, small correctness fixes** (F3, F4, F6). Each is a one-to-five line fix
   plus a focused test.
3. **Slice 3, lifecycle** (F7). Add `closeEvent` teardown and `PlayerWidget.shutdown()`,
   test with a fake player, then check manually with real VLC.
4. **Slice 4, hardening** (F8, F9). Add download and decompression budgets and file
   modes.
5. **Slice 5, CI and dependencies** (F10, F11). These need explicit approval for
   `.github/` and `requirements*.txt` edits and a networked `pip-audit`. Fix the docs
   drift in the same pass.
6. **Later:** F13, F14, F15 and the small items in §4.

## 10. Things not to do yet

- Don't move search or filtering off the GUI thread or add incremental model
  population. The measurements in §7 show no need.
- Don't introduce an ORM, a migration framework or Alembic. Add `PRAGMA user_version`
  only when the next schema change lands (F13).
- Don't move credentials to an OS keyring before F9's file modes are done. It adds a
  platform dependency and changes restore semantics.
- Don't replace `requests` with an async client to get cancellation. Bounded downloads
  (F8) and teardown waits (F7) cover the practical risk.
- Don't make mypy blocking in one step with 75 errors outstanding. Ratchet it instead.
- Don't add packaging or installer work until the input-robustness and lifecycle slices
  are done.

## 11. Highest-value next step

Implement **Slice 1 (input robustness)** as one focused change:

- In `EPGRepository.save_all`, use `INSERT OR REPLACE` with `executemany`, and dedupe
  `(channel, start)` in `EPGParser`.
- Map `ET.ParseError` to `ValueError`.
- Try UTF-16 only when a BOM is present, with the order `utf-8-sig`, `utf-8`, `cp1252`,
  `iso-8859-1`.
- Accept unquoted M3U attribute values.
- Add regression tests:
  - a duplicate programme loads successfully;
  - malformed XML raises `ParsingError`;
  - even-length and odd-length cp1252 playlists parse with correct names;
  - a UTF-16 playlist with a BOM still parses;
  - `tvg-id=foo` populates `epg_id`.

Verify with `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_m3u_parser.py tests/test_epg_now_next.py`
first, then the full gate:
`.venv/bin/ruff check . && .venv/bin/ruff format --check . && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`.
