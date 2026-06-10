# UI / Layout Audit — Simple IPTV Player (branch `v2`)

**Date:** 2026-06-10
**Scope:** `ui/windows/main_window.py`, `ui/widgets/*` (right_panel, left_panel, player_widget, notification, menu_bar, epg_widget, loading_overlay, search_bar, channel_list_view), `ui/styles/*` (themes, styles), `ui/dialogs/*` (playlist_manager_dialog, xtream_source_dialog).
**Method:** Static code review (no rendered screenshots). Contrast ratios computed programmatically against WCAG 2.1 AA (4.5:1 normal text, 3:1 large/bold ≥14pt).

---

## Overall Verdict: **B (Good, with a few real accessibility and architecture gaps)**

This is a notably well-crafted PyQt6 UI for a v2 desktop app. Strengths:

- A genuine **token-based theme system** (`Themes._DARK` / `_LIGHT`) with semantic names (`panel`, `panel_alt`, `accent_soft`, `border_soft`, tone-based chips) applied through one generated QSS sheet. This is far better than the scattered-stylesheet pattern most Qt apps end up with.
- **Consistent spacing rhythm** — outer margins 18, card padding 14–16, inter-widget spacing 10–14 — applied uniformly across panels, cards, and dialogs.
- **Real empty/loading/error states everywhere**: `CollectionStateWidget` for lists, `LoadingOverlay` with progress, EPG loading/empty states, player placeholder + status overlay, status chips with tones. This is the part most apps skip.
- Thoughtful UX details: search debounce (200ms), notification de-dup + queueing, visible-row-only EPG refresh, model/delegate virtualized channel list for large playlists, splitter size persistence, exponential-backoff stream reconnect.

What holds it back from an A:

1. The **light theme fails WCAG AA** on every status chip and badge.
2. **Two parallel channel-row implementations** (painted delegate vs. widget rows) that will visually drift.
3. **Hardcoded colors that bypass the theme system** (notifications, Xtream error label, delegate fallback logos).
4. **Fixed pixel metrics in the delegate** that break under larger system fonts / HiDPI font scaling.
5. **No visible keyboard focus indication** for most interactive controls (lists explicitly set `outline: none`).

---

## 🔴 Critical

### C1. Light theme status chips and badges fail WCAG AA contrast
**Location:** `ui/styles/themes.py` `_LIGHT` tokens + chip rules (lines 184–212, 344–359).
**Problem:** Chips (`playback_state_chip`, `playlist_status_chip`, `epg_status_chip`) and channel badges render tone colors on `accent_soft` (`#d8f3ef`). Measured ratios in light mode:

| Pair | Ratio | AA (4.5:1) |
|---|---|---|
| accent `#129d8d` on `#d8f3ef` | 2.89:1 | ❌ |
| warning `#b57f29` on `#d8f3ef` | 2.98:1 | ❌ |
| success `#2f9d67` on `#d8f3ef` | 2.93:1 | ❌ |
| error `#c45160` on `#d8f3ef` | 3.83:1 | ❌ |
| tab_text_muted `#738a97` on tab `#edf4f7` | 3.25:1 | ❌ |

The dark theme passes everywhere (5.3–6.5:1) — only the light palette is broken. These chips carry primary status information (Live/Buffering/Error, playlist state), so this is not cosmetic.
**Fix:** Darken the light tone colors ~25–30% so they hit ≥4.5:1 on `#d8f3ef`:

```python
# themes.py _LIGHT — replace:
"accent": "#0c7a6d",        # was #129d8d  -> ~4.6:1 on accent_soft
"warning": "#8a5f17",       # was #b57f29
"error": "#b23a4a",         # was #c45160
"success": "#1f7a4d",       # was #2f9d67
"tab_text_muted": "#5a6f7c" # was #738a97
```
Keep the current brighter values as separate `*_strong`/decorative tokens if you need them for borders or fills.
**Impact:** Light mode becomes readable for low-vision users and in bright environments; status information is no longer guesswork.

### C2. Channel row delegate uses fixed pixel metrics — clips text under font scaling / HiDPI
**Location:** `ui/widgets/channel_list_view.py` `ChannelRowDelegate` (lines 146–257): `ROW_HEIGHT = 88`, `title_rect ... 22`, `top() + 26`, `top() + 48`, badge height `20`; also `left_panel.py:563` `item.setSizeHint(QSize(100, 88))`.
**Problem:** All vertical geometry is hardcoded for a ~13px font. If the user's system font is larger (KDE/GNOME font scaling, accessibility settings, 125–150% DPI text scaling), the three text lines overlap or clip inside the 88px row. The widget-based rows in favorites/recent have `wordWrap(True)` titles inside a fixed 88px item — long names silently clip there too.
**Fix:** Derive metrics from `QFontMetrics` once per paint/sizeHint:

```python
def sizeHint(self, option, index):
    fm = QFontMetrics(option.font)
    line = fm.height()
    return QSize(option.rect.width(), max(72, 3 * line + 2 * 4 + 24))  # 3 lines + gaps + padding
```
And in `paint()`, compute `title_rect`/`subtitle_rect`/`meta_rect` tops from `fm.height()` instead of 0/26/48. Same for the `QSize(100, 88)` size hints in `left_panel._append_channels`.
**Impact:** Rows stay readable for every user; no clipped titles on long channel names.

### C3. No visible keyboard focus indicator on most controls; lists disable outlines
**Location:** `ui/styles/themes.py` — `QListWidget, QListView { outline: none; }` (line 306); no `:focus` rules for `QPushButton`, `QTabBar::tab`, `QCheckBox`, `QSlider`; only `QLineEdit:focus`/`QComboBox:focus` exist.
**Problem:** A keyboard user tabbing through the control bar (Play/Stop/Retry/Mute/Favorite/Fullscreen) or the channel lists gets no visual indication of where focus is. `outline: none` on the lists removes the only default cue. This fails WCAG 2.4.7 (Focus Visible).
**Fix:** Add to the generated theme:

```css
QPushButton:focus {{ border: 2px solid {accent}; padding: 9px 15px; }}
QListView:focus, QListWidget:focus {{ border: 1px solid {accent}; }}
QTabBar::tab:focus {{ border: 1px solid {accent}; }}
QCheckBox:focus {{ outline: 1px solid {accent}; }}
QSlider::handle:horizontal:focus {{ background-color: {accent_strong}; }}
```
(For lists, painted selection in the delegate already marks the current row — keep `outline: none` on items but restore a focus border on the view itself, as above.)
**Impact:** App becomes operable by keyboard; required for any accessibility claim.

### C4. Notification toast can overflow the window width
**Location:** `ui/widgets/notification.py` `_display_message()` (line 85–88) and `_reposition()`.
**Problem:** `setWordWrap(True)` + `adjustSize()` on a QLabel without a width constraint: `sizeHint()` for a wrapping label is computed for the *unwrapped* single-line width. A long error message (stream URLs, parser errors are passed verbatim via `_on_error`) produces a toast wider than the window; `_reposition()` then computes a negative x and the text runs off both edges.
**Fix:** Clamp to the parent before showing:

```python
def _display_message(self, message, notification_type, duration):
    ...
    self.setText(message)
    parent = self.parent()
    max_w = max(280, (parent.width() if parent else 600) - 96)
    self.setMaximumWidth(max_w)
    self.setFixedWidth(min(self.sizeHint().width() + 32, max_w))
    self.adjustSize()
    ...
```
**Impact:** Error messages — exactly the ones users must read — stay on screen.

### C5. Minimum window size is smaller than the layout's true minimum
**Location:** `main_window.py:79` `setMinimumSize(980, 640)`; `left_panel.py:249` `setMinimumWidth(340)`; `player_widget.py:85` `setMinimumSize(540, 340)`.
**Problem:** Horizontal minimum actually required: 340 (left) + 540 (player) + 36 (right panel margins) + 28 (player_surface margins) + 36 (central margins) + ~6 (splitter handle) ≈ **986px**, exceeding the 980px window minimum. Vertically it is worse: now-playing card (6 stacked labels, ~180px) + player (340 min) + control bar (~110) + margins ≈ 700px against a 640px minimum — at minimum height the splitter/right panel must violate child minimums, and Qt responds by clipping or letting the player surface collapse below its minimum.
**Fix:** Either raise the minimum to `setMinimumSize(1024, 720)`, or reduce the player minimum to `480x270` (still 16:9) and make the now-playing card collapsible (see I4).
**Impact:** No silently broken layout at the advertised minimum size; small-screen laptops get a working window.

---

## 🟡 Important

### I1. Two parallel channel-row implementations will drift apart
**Location:** `ui/widgets/left_panel.py` `ChannelListItemWidget` (widget-based, used by Favorites/Recent `QListWidget`s) vs. `ui/widgets/channel_list_view.py` `ChannelRowDelegate` (painted, used by the main Channels list).
**Problem:** The same visual component — logo, title, subtitle, meta, LIVE/FAV badges, selection ring — exists twice with independent geometry, fonts, and badge rendering (QSS-styled `ChannelBadge` vs. hand-painted rounded rects). Today they look similar; any future tweak (badge color, row height, hover) must be made twice and inevitably won't be. The widget version also has different hover behavior (QSS `::item:hover`) from the delegate's `State_MouseOver` paint.
**Fix:** Use `ChannelListView` + `ChannelRowDelegate` for all three tabs. Favorites and Recent are just small channel lists — `ChannelListModel.set_channels()` already supports favorite keys and current-channel highlighting; meta strings ("Last played ...", "Source ...") can be passed via a `meta_override` per channel or an extra model role. This deletes ~150 lines (`ChannelListItemWidget`, `_populate_list`, `_append_channels`, `_channel_item_widget`, `_sync_list_selection_styles`, `_select_channel`).
**Impact:** One source of truth for the most-seen component in the app; consistent hover/selection; less code.

### I2. Hardcoded colors bypass the theme system (notifications never theme-switch)
**Locations:**
- `ui/widgets/notification.py:24–29` — `STYLES` hardcodes 12 dark-palette hex values. In light mode, toasts stay dark; the colors also duplicate (approximately, not exactly) `accent_soft`/`warning`/`error` tokens.
- `ui/dialogs/xtream_source_dialog.py:67` — `setStyleSheet("color: #d24d57;")` for the error label: 4.25:1 on light (borderline), **3.77:1 on dark panel — fails AA**, and matches neither theme's `error` token.
- `ui/widgets/left_panel.py:105` — fallback-logo foreground `QColor("#0a171d")` hardcoded.
- `ui/widgets/channel_list_view.py:152` — `self._tokens = Themes._DARK` reads a private dict; the delegate defaults to dark even when the app starts in light mode unless `set_theme_mode` happens to be called (it is, but only because `MainWindow._apply_theme` does so — a fragile implicit contract).
**Fix:** Expose tokens publicly: `Themes.tokens(mode: str) -> dict`. Notification: build `STYLES` from the active token set, or better, give the toast `stateTone` properties and style it in the theme QSS like the chips (it already has `objectName "notification_toast"` and a rule in themes.py — the inline stylesheet *overrides* that rule, so the theme rule is dead code today). Xtream dialog: `self.error_label.setObjectName("playlist_feedback"); self.error_label.setProperty("stateTone", "error")` and delete the inline stylesheet.
**Impact:** Light theme actually looks like a light theme end-to-end; one palette to maintain.

### I3. Toolbar status chips have unbounded width and no eliding
**Location:** `main_window.py:132–141` + progress text like `"Playlist: rendering 12,345/67,890"` and `"EPG: {message}"` where `message` is arbitrary progress text.
**Problem:** The chips share the toolbar row with the EPG URL input (`stretch=1`). Long status text (URL-derived messages, big channel counts, error strings) squeezes the input toward zero width and can push the toolbar to wrap/clip. There's no `maximumWidth` or eliding.
**Fix:**
```python
for chip in (self.playlist_status_label, self.epg_status_label):
    chip.setMaximumWidth(280)
    # and elide in _set_status_chip:
metrics = label.fontMetrics()
label.setText(metrics.elidedText(text, Qt.TextElideMode.ElideRight, 260))
label.setToolTip(text)
```
**Impact:** Toolbar stays stable during loading; full text remains available via tooltip.

### I4. "Now Playing" card: six stacked labels with weak hierarchy and redundant filler text
**Location:** `ui/widgets/right_panel.py:25–74` and `set_source_context()`/`set_now_playing()`.
**Problem:** The card stacks title, meta, program title, program description, `stream_detail_label`, and `playback_detail_label`. Two of those are instructional filler ("Use the player controls to mute, retry, copy the stream URL..." / "Stream URL available. Use Copy URL to share or inspect it.") that competes with actual content, consumes ~60–80px of permanent vertical space (worsening C5), and restates what the buttons already say. `playback_detail_label` duplicates the chip's state in sentence form.
**Fix:** Remove `stream_detail_label` entirely (the Copy URL button is self-explanatory; disable it when no URL). Merge `playback_detail_label` into the chip's tooltip, or show it only for warning/error states:
```python
self.playback_detail_label.setVisible(state in ("reconnecting", "error", "buffering"))
```
**Impact:** Clear hierarchy (channel → program → description), ~70px reclaimed for video, less visual noise.

### I5. Left panel vertical budget: EPG widget's fixed 280px minimum crushes the channel list
**Location:** `ui/widgets/epg_widget.py:16` `setMinimumHeight(280)`; `left_panel.py` layout (title + filter card ~150px + tabs + status label + EPG).
**Problem:** At 640–720px window heights, the fixed 280px EPG block plus the filter card leaves the channel list (the panel's primary content, `stretch=1`) with ~150–200px — about two rows. The hierarchy is inverted: the guide for the *current* channel dominates the panel whose job is browsing.
**Fix:** Reduce to `setMinimumHeight(160)` and/or put `tabs` and `epg_widget` in a vertical `QSplitter` so users control the split; persist it like the main splitter. Alternative: move Now/Next into the right panel's now-playing card (it's about the playing channel anyway) and keep only "Coming Up" on the left.
**Impact:** The channel list — the core browsing surface — gets usable height on small windows.

### I6. LoadingOverlay blocks all interaction but offers no Cancel, despite cancel support existing
**Location:** `ui/widgets/loading_overlay.py`; `main_window.py` `_set_main_interaction_enabled(False)`; controllers emit `loading_cancelled`.
**Problem:** During a slow/hung remote playlist load the entire UI (menu bar included) is disabled and the overlay has no escape hatch. The plumbing for cancellation exists (`loading_cancelled` signals are connected) but nothing in the UI can trigger it. A stalled HTTP fetch leaves the user with only force-quit.
**Fix:** Add a ghost "Cancel" `QPushButton` to `busy_overlay_card`, expose `cancel_requested = pyqtSignal()`, and wire it to the playlist/EPG controllers' cancel path. Also avoid disabling the menu bar (keep File > Exit usable).
**Impact:** Removes the worst-case UX trap in the app.

### I7. Duplicated helpers and dead/overlapping style code
**Locations:**
- `_format_display_time` duplicated **4×**: `right_panel.py:230`, `left_panel.py:635`, `epg_widget.py:121`, `channel_list_view.py:140`.
- `ui/styles/styles.py` `ToolbarStyle.TOOLBAR` sets only `spacing: 12px`, then `themes.py:132` styles the same `QToolBar#main_toolbar` (and the inline sheet overrides the theme rule's spacing — coincidentally equal today).
- `themes.py:414` `QLabel#notification_toast` rule is dead (always overridden by the inline sheet, see I2).
- `left_panel.populate_channels_incrementally()` is a pure pass-through to `set_channel_results` (vestigial API).
**Fix:** Move `format_display_time` to e.g. `ui/utils/time_format.py`; delete `ToolbarStyle` (fold spacing into the theme rule) and the pass-through method.
**Impact:** Maintainability; prevents the four time formatters from diverging (one already differs in whitespace handling risk).

### I8. Mute/Favorite button state is string-synchronized from three call sites
**Location:** `main_window.py:105, 568` (`mute_button.setText("Unmute"/"Mute")`), `right_panel` has no ownership; `_refresh_favorite_button` similarly toggles "Favorite"/"Unfavorite" text.
**Problem:** Button label *is* the state store, mutated from multiple places. Text-swapping buttons also shift layout (different widths) and "Unfavorite" is awkward. No pressed/checked visual state.
**Fix:** Make both buttons checkable and style the checked state; keep labels stable:
```python
self.mute_button.setCheckable(True)   # label stays "Mute"
# themes.py:
QPushButton:checked {{ background-color: {accent_soft}; color: {accent}; border: 1px solid {accent}; }}
```
Expose `right_panel.set_muted(bool)` / `set_favorite(bool)` so MainWindow sets state, not strings.
**Impact:** No layout jitter, clearer state, single source of truth.

---

## 🟢 Polish

### P1. Style the splitter handle and scrollbars to match the design language
Default Qt scrollbars and the invisible 4px splitter handle clash with the rounded, soft-bordered aesthetic. Add to `themes.py`:
```css
QSplitter::handle:horizontal {{ width: 10px; background: transparent; }}
QSplitter::handle:horizontal:hover {{ background: {surface_hover}; border-radius: 4px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 5px; min-height: 32px; }}
QScrollBar::handle:vertical:hover {{ background: {accent}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
```

### P2. Volume slider gives no value feedback
`right_panel.py:129` — add a live percentage label (or tooltip on drag): `self.volume_value = QLabel("100%")` updated in `_on_volume_changed`. Also reflect mute by disabling/dimming the slider.

### P3. Player surface margins waste space around video
`right_panel.py:79` pads the video 14px inside `player_surface`, producing a light ring around the (black) video. Set margins to 0 and give `player_video_surface` `background-color: #000; border-radius: 14px;` so video sits edge-to-edge in the card.

### P4. Border-radius scale has five values (18/16/14/12/10)
Panels 18, toolbar/search 16, inputs/buttons/rows 14, chips/tabs/logos 12, badges 10. Workable, but collapsing to three (outer 16, controls 12, badges 8) would tighten the look. Define them as named tokens in `Themes` rather than literals repeated ~25 times in the QSS string.

### P5. Keyboard shortcuts for the player
Only menu actions have shortcuts. Add space = play/pause, `M` = mute, `F`/double-click = fullscreen (double-click exists), `Ctrl+L` = focus search. Cheap, high-value for a TV app.

### P6. `QMessageBox` for Channel Info breaks the visual language
`main_window.py:609` uses a stock message box with a newline-joined string. A small styled dialog (or reusing the details-card pattern from the playlist manager) would match; at minimum, use `QMessageBox.setInformativeText` and rich text for label/value formatting.

### P7. Fullscreen reparenting is brittle
`player_widget.py:301–332` manually removes/reinserts itself into the parent layout, caching index/stretch. It works, but a `QStackedLayout` host or `windowHandle()->setVisibility` approach survives layout refactors better. Also `keyPressEvent` in `PlayerWidget` swallows non-Escape keys without calling `super()` when not fullscreen — call `super().keyPressEvent(event)` unconditionally at the end.

### P8. Empty-state copy duplication
"No channels match / Adjust the category or search filters..." appears as default args in three method signatures in `left_panel.py`. Hoist to module constants.

---

## Quick Wins (under an hour total)

1. **Darken the five light-theme tone colors** (C1) — one dict edit, fixes every chip/badge contrast failure.
2. **Clamp notification width** (C4) — 4 lines in `notification.py`.
3. **Add `:focus` rules** to the theme QSS (C3) — pure CSS, no logic.
4. **Delete `stream_detail_label` + conditional `playback_detail_label`** (I4) — reclaims vertical space immediately.
5. **Elide + tooltip on toolbar chips** (I3) — 5 lines in `_set_status_chip`.
6. **Set Xtream error label to the themed `stateTone` pattern** (I2) — removes the worst hardcoded color.

## Suggested order of attack
1. C1 + C3 (accessibility, trivial) → 2. C4, I3 (overflow safety) → 3. I4 + I5 + C5 (vertical-space cluster — do together) → 4. I2 (theme unification) → 5. I1 (delegate consolidation — biggest refactor, do last with the most attention).
