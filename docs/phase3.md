## Phase 3 backlog

### P0 --- fix correctness and reliability first

1.  **Fix the playback retry loop**

    The biggest functional issue is in `PlayerWidget`: `_handle_playback_error()` increments `reconnect_attempts`, but `_reconnect()` calls `play()`, and `play()` immediately resets `reconnect_attempts = 0`. That means the retry cap is effectively broken and reconnects can loop forever under persistent failure. This should be refactored so reconnect state is only reset after a successful `media_playing` event, not before every retry attempt.

2.  **Stop swallowing database initialization failures**

    `SQLiteConnection._init_database()` catches exceptions and only logs them instead of failing fast. That can leave the app booted with a broken persistence layer and produce misleading downstream errors later in controllers/services. Database initialization should raise on failure and surface a startup error dialog.

3.  **Make channel identity source-aware**

    `Channel.__eq__` and `__hash__` are based only on `url`, and favorites are also keyed only by `url`. That is fragile for IPTV, because the same stream URL can appear in multiple playlists with different names, groups, logos, or EPG mappings. Identity should be based on a composite key such as `(url, playlist_path)` or a generated source-specific id.

4.  **Separate parse errors from persistence errors**

    `EPGService.load_epg_from_path()` catches broad exceptions and rethrows them as `ParsingError`, even when the real failure might be repository/database persistence. That will produce the wrong user-facing error and complicate debugging. Parsing, download, and persistence failures should stay distinct.

5.  **Unify EPG time behavior**

    `EPGService.get_program_for_channel(channel_id, current_time)` passes `current_time` only when using in-memory `_channels`, but the repository fallback ignores `current_time` completely and always uses `datetime.now()`. That creates inconsistent behavior and makes testing harder. The repository API should accept an explicit timestamp too.

6.  **Validate playlist manager operations**

    The playlist manager currently allows adding duplicates, editing paths freely, and removing entries without active-playlist safeguards. It also rebuilds playlist objects from only `name/path/is_url`, which is workable only because metadata is later preserved by path in the repository. That is too indirect and brittle. Add duplicate detection, invalid-path/URL validation, and protection when removing or editing the active playlist.

### P1 --- remove UI freezes and state inconsistencies

1.  **Move playlist and EPG loading off the UI thread**

    Remote playlist downloads, EPG downloads, large XML parsing, and database writes are all synchronous right now. Since controllers call services directly and the services use blocking `requests.get(...)`, the UI can freeze during larger loads. Phase 3 should introduce worker threads or `QThreadPool` jobs for playlist/EPG load flows, with cancellable progress states.

2.  **Persist more UI state**

    On close, the app saves theme, window width/height, and mute state, but not splitter sizes, active tab, selected category, search text, sort mode changes beyond current setting save, or last visible panel state. Persisting those would make the app feel much more "real" on reopen.

3.  **Fix stale playback detail text**

    `RightPanel.set_playback_state()` only updates `playback_detail_label` when `detail` is non-empty, so stale text can survive into later states. That is small but noticeable. Every state change should explicitly set the detail label, even if that means clearing it.

4.  **Consolidate channel filtering/search logic**

    Search/filter behavior currently lives in `MainWindow._resolve_visible_channels()`, while `PlaylistController.search_channels()` implements a different, simpler search that only checks names. That is a maintenance trap. There should be one canonical query/filter pipeline.

5.  **Harden fullscreen behavior**

    Fullscreen currently hides every visible widget in the window tree, reparents the player, and restores visibility by a temporary `was_visible` property. It works, but it is easy to break with future UI additions and can interact badly with dialogs/toolbars. This should be turned into a more explicit fullscreen shell or dedicated player window mode.

6.  **Improve Linux/Wayland playback embedding robustness**

    On Linux, VLC is bound with `set_xwindow(int(self.winId()))`. That is historically X11-oriented and can be fragile under Wayland environments. This is a platform-risk area that should be tested and possibly wrapped with better backend detection/fallback behavior.

### P1 --- improve parsing and data quality

1.  **Make the EPG parser more compatible**

    The XMLTV parser strips namespace only from the root tag check, but uses plain `find("title")`, `find("desc")`, and `find("category")` on children. Some XMLTV feeds with namespaces may not parse correctly. It also lacks support for common compressed EPG feeds like `.xml.gz`.

2.  **Make timezone handling explicit**

    `EPGParser.parse_date()` converts offset timestamps by subtracting the offset and stores naive datetimes. Since the rest of the app also uses naive `datetime.now()`, this may appear to work, but it is brittle around DST and cross-timezone assumptions. Phase 3 should standardize on timezone-aware UTC internally and convert only in the UI layer.

3.  **Strengthen M3U parsing**

    The parser is reasonable, but still optimistic: only a few encodings are supported, attribute parsing assumes double quotes, entries without proper `#EXTINF` context are silently skipped, and malformed `tvg-chno` / `tvg-shift` values can invalidate entries. This is a good place to improve resilience and produce structured parse warnings.

### P2 --- UX improvements that will noticeably improve the product

1.  **Replace plain text channel rows with richer list items**

    Right now rows are rendered as plain `QListWidgetItem` text with `[PLAYING]` and `[FAV]` markers. Phase 3 should move to custom item widgets or delegates showing channel logo, name, group, current program, and lightweight status badges. That would materially improve scanability.

2.  **Upgrade the "Now Playing" controls**

    The right panel has Play, Stop, Favorite, and volume only. Good Phase 3 additions would be mute, retry now, copy stream URL, fullscreen button, and possibly an "open source playlist" or "channel info" action.

3.  **Add loading and empty states instead of relying on toast messages**

    The app currently leans heavily on notifications and status chips. For bigger operations like playlist load and EPG refresh, add visible inline loading states and placeholders in the channel/EPG panels.

4.  **Make notifications smarter**

    `NotificationWidget` positions itself only when shown and does not appear to re-center on parent resize. It would be better to support queueing, deduping, resize-aware repositioning, and a consistent placement system.

5.  **Improve playlist manager usability**

    The dialog already has a solid structure, but it needs validation feedback, duplicate detection, last validation result, "test URL/file" behavior, and clearer active playlist affordances. It is close to useful, but still feels internal rather than productized.

6.  **Expose more playback/EPG context in the UI**

    The app already stores channel count, last loaded time, status, and EPG loaded timestamp. Surface more of that directly: EPG source type, last refresh source, number of programs parsed, playlist validation state, and last error.

### P2 --- codebase cleanup and maintenance

1.  **Fix outdated docs and packaging metadata**

    The README still references the old `simple_iptv/...` structure and outdated run command, and `MANIFEST.in` points at `simple_iptv/playback/*.py` even though the actual code is now under `app/`, `core/`, `infra/`, and `ui/`. This should be cleaned up before shipping or sharing the repo further.

2.  **Remove dead or legacy dependency drift**

    `requirements.txt` includes both PyQt5 and PyQt6 even though the code imports PyQt6. That increases install weight and confusion for no obvious benefit.

3.  **Tighten startup/bootstrap behavior**

    `app/main.py` bootstraps the app cleanly enough, but it would benefit from a top-level exception hook, better startup diagnostics, and graceful handling for missing VLC or broken DB init before the main window opens.

4.  **Expand test coverage beyond smoke/service tests**

    Current tests cover smoke imports, parser basics, settings sync, history round-trips, and a playlist download failure path. What is missing are UI/controller/integration tests for playlist switching, retry behavior, fullscreen enter/exit, favorites/history interactions, and migration failures.
