# Performance Audit

Point-in-time report, 2026-10-18, branch `v2` (HEAD `e19760c`). Mode: INVESTIGATE — measured and
recommended only; no application code was changed. Re-measure before relying on these numbers.

## Summary

Three things are worth fixing, ranked by user-visible impact:

1. **Every launch spends ~1 s of CPU building channel objects** — ~0.9 s of it is avoidable at near-zero risk.
2. **EPG loading is slow and memory-heavy** — a 385k-programme guide takes ~10.6 s and peaks near 800 MB RSS.
3. **The channel list resets its scroll position during large-list scrolling** — reproduced offscreen only, and
   latent for the current saved settings (single category selected).

## Baseline

**Metrics:** wall time / CPU for user-visible operations (launch → channels, EPG load, search, scroll),
UI-thread starvation during background work, peak RSS.

**Workload:** shaped to the real source in `iptv_player.log`: an Xtream source with **57,033 channels in
915 categories**, whose fetch → success takes **2.1–2.7 s** per launch. Synthetic data:

- Xtream JSON: 19.6 MB (`get_live_streams`), plus categories and auth payloads
- Same catalogue as M3U: 12.4 MB
- XMLTV: 108 MB (13 MB gzipped), 2,000 channels × 7 days, 385,012 programmes

**Environment:** AMD Ryzen 7 5700X3D (16 threads), Python 3.14.8 (CI targets 3.12), Qt 6.8.1 / PyQt 6.8.0,
`QT_QPA_PLATFORM=offscreen` for UI numbers, mocked HTTP (`requests` session patched; local
`ThreadingHTTPServer` for logo tests), temporary `HOME`. `~/.simple_iptv` was only read (row counts and the
list settings `selected_category`, `channel_sort_mode`, `show_now_playing_in_list`, `search_text`).

| Operation | Result |
|---|---|
| Xtream fetch + mapping, CPU only | **1,040 ms** (of which `json.loads` 148 ms) |
| EPG load, 385k programmes (parse + `save_all`) | **10.6 s**; peak RSS **802 MB**, ~740 MB still held afterwards |
| M3U parse, 57k entries | 706 ms |
| Main-thread wake delay during background loads | p50 7 ms; max **126 ms** (Xtream), **425 ms** (EPG) |
| `_on_playlist_loaded` with 57k rows, incl. first paint | 47 ms |
| Search / sort / `_refresh_channel_list` | 8–16 ms (`favorites_first` sort 46 ms) |
| Scroll, per page painted | ~3.3 ms |
| `save_setting` / `get_favorites` | 0.7 ms / 0.6 ms |
| `import app.main` / `create_window()` + show | 136 ms / 116 ms |

## Bottlenecks

### 1. Xtream mapping: ~1 s CPU per launch

Roughly 40–50% of the 2.1–2.7 s seen in the log; the rest is network.

- **562 ms** — `_build_live_stream_url` (`infra/providers/xtream_client.py:338`) calls
  `credentials.normalized()` for each of the 57k channels (~3 `urlparse` calls each).
- **524 ms** — `redacted_summary()` is passed as an argument to `logger.debug` inside the loop
  (`xtream_client.py:116-121`). The argument is evaluated even though DEBUG is suppressed at INFO.
- **148 ms** — `json.loads` of the 19.6 MB body: one C call holding the GIL, which explains the 126 ms
  main-thread stall. Not removable by hoisting.

### 2. EPG parse: ~9.5 s, plus ~1.4 s `save_all`

- **5.1 s** — `EPGParser.parse_date` (`infra/parsers/epg_parser.py:36`) runs 770k times; each call does
  `datetime.strptime`, an uncompiled `re.match`, and builds a `timezone` object.
- **~1.0 s** — cyclic GC: 388 collections, worst gen-2 pause 392 ms (matches the 425 ms main-thread stall).
- **1.4–1.7 s** — `ET.parse` builds the full tree. Tree alone: 629 MB RSS; `iterparse` + `clear()` that
  discards everything: 52 MB (a realistic streaming parse that keeps `Program` objects is ~220 MB).
- **~1.3 s** — `root.iter()` + `_local_name` walk all ~3M elements, not just `<programme>` children.
- After load, RSS stays ~740 MB (live `Program` objects plus allocator memory not returned to the OS).
- The local `epg_data` table is currently empty, so this cost applies once an EPG is used.

### 3. Channel list re-lays out every row on a single-row update

Any `dataChanged` on `ChannelListModel` makes `QListView` (Batched layout, 256 rows per pass) discard and
rebuild the layout of all rows. While it rebuilds, the scroll range shrinks to the first batch
(256 × 70 px − viewport = 17,282 px) and the scroll position is clamped to about row 246.

- Triggers: logo arrival → `notify_logo_changed` (`ui/widgets/channel_list_view.py:136`), and EPG subtitle
  refresh → `update_current_programs` (`channel_list_view.py:121`), which runs after every scroll stop once
  EPG is loaded.
- Cost: 80–120 ms of UI-thread layout per trigger, in addition to the position reset.
- Reproduced deterministically in isolated processes with the real `ChannelListView` (offscreen), for both
  visible and offscreen changed rows. **Not yet confirmed on a real display.**
- Latent for the current settings: the saved category is a single category and search is scoped to it, so it
  shows up only on "All" or result lists longer than 256 rows.

### 4. Logo loading

- Every painted row starts its own HTTP request (`ChannelLogoProvider.request_logo`,
  `ui/widgets/left_panel.py:64`); a 120-page scroll issued 963 requests.
- Requests for rows scrolled past are never cancelled; visible rows queue behind them.
- No `QNetworkDiskCache`: every launch re-downloads all logos.
- The 500-entry in-memory LRU is evicted within one fast scroll.

## Options considered

Prototyped in scratch only; equivalence checked where stated.

| # | Option | Measured / expected effect | Risk | Complexity |
|---|---|---|---|---|
| A | Normalize credentials once, build the URL prefix outside the loop; drop the per-item `redacted_summary()` debug argument | 1,040 → ~200 ms per launch (URL building 562 → 46 ms; URLs byte-identical) | Very low | Trivial |
| B | `parse_date` via integer slicing + precompiled regex | 5.1 s → 1.6 s (matches current output on edge cases and 715 real values) | Low | Small |
| C | `gc.freeze()` / `gc.disable()` around the EPG parse, restored in `finally` | −1.0 s; removes the 392 ms stall | Low | Small |
| D | Iterate only `<programme>` elements, or stream with `iterparse` + `clear()` | −1.3 s CPU; tree memory 629 MB → small (realistic total ~220 MB) | Medium | Medium |
| E | Route data-only updates to `QAbstractItemView.dataChanged`, bypassing `QListView`'s relayout | 0.06 ms per update, no scroll reset | Medium: relies on Qt internals; changed-row repaint not yet verified | Small |
| E′ | Switch the list to `SinglePass` layout | No reset, but 85 ms per update — **rejected** | — | — |
| F | `QNetworkDiskCache` for logos; cancel or defer requests for rows not on screen | Fewer repeat downloads; faster visible logos after scrolling (not measured) | Low–Medium | Medium |
| G | Cache the Xtream catalogue, refresh in the background | Removes ~2.3 s network from launch | **High** — see Tradeoffs | High |

A, B and C are the recommended first step: low risk, ~0.9 s saved per launch and ~4.5 s per EPG load.

## Tradeoffs

- **A–C:** none meaningful.
- **D:** changes memory behaviour; namespace handling (`_local_name`) must be preserved.
- **E:** depends on Qt's internal `QListView` behaviour; needs a regression test on scroll position.
- **G:** Xtream stream URLs carry the password in the path, so a cache must store `stream_id` and rebuild
  URLs from credentials, never store raw URLs. Also introduces staleness.

## Not bottlenecks — leave alone

Search, sort and the 200 ms search debounce; settings writes and favorites reads; scroll painting; the three
list refreshes in `_on_epg_loaded` (35 ms); `Playlist` index build (29 ms); EPG lookups for visible rows
(<0.1 ms).

## Next steps

1. Confirm bottleneck 3 in the real app: select "All", scroll past row 250, wait for logos.
2. Measure UI stalls with `app.exec()` and the real `QThreadPool`; the worker-thread probe is a lower bound.
3. Measure visible-logo latency after a fast scroll once option E is in place (bottleneck 3 confounded it).
4. Re-check EPG numbers against a real guide once one is loaded.

Separately: a security hook suggested `defusedxml` for the XMLTV parser. That is a dependency change and
needs explicit approval.

## Reproducing

The benchmark harness lived in a session scratchpad and is not kept in the repo. Method: generate synthetic
data with the sizes above, patch `XtreamClient.session.get` with a fake streaming response, run each phase in
its own process with `.venv/bin/python`, a temporary `HOME`, and `QT_QPA_PLATFORM=offscreen`, and report the
median of 5–7 runs.
