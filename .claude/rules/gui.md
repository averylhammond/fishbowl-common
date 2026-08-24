---
paths:
  - "fishbowl_common/gui/**"
  - "tests/gui/**"
---

# `fishbowl_common.gui`

The themed tkinter layer both apps share, all of it re-exported from
`fishbowl_common/gui/__init__.py`.

**Every window snapshots the active theme and font when it opens**, so it stays styled
consistently with the main window behind it. `ThemedSubwindow` is the `tk.Toplevel` base that
does the snapshotting; `MessageWindow`, `AboutWindow`, `FileEditorWindow`, `PatchNotesWindow` and
`UpdateWindow` all extend it, and `Tooltip` is the one that does not.

## Rules that are not obvious from the code

- **Only `RED` is re-exported from `color_theme`'s palette.** It is the one bare color a consumer
  applies directly (the Exit button); everything else reaches a window through a `Theme`. Do not
  widen the palette's public surface to save a consumer a lookup.
- **`AboutWindow` takes `app_name` and `version` injected, and that is the whole reason a window
  this app-specific is allowed to live in a shared package.** A window that cannot be made
  generic by injection belongs in the app's own `source/gui/`, not here.
- **`Tooltip` binds with `add="+"`, and that flag is load-bearing downstream.**
  `FishbowlInventoryTool` attaches a tooltip to every column checkbutton, each of which already
  carries a `command` that persists that column's state. A binding without `add="+"` replaces it,
  silently breaking the checkbox rather than raising anything.
  - `Tooltip` is deliberately **not** a `ThemedSubwindow`: it builds its own borderless
    `Toplevel` on hover, after `SHOW_DELAY_MS` (500ms) so a pointer merely crossing the widget
    never flashes a tip. `update_style()` restyles it in place.
- **`UpdateWindow._send_to_release_page()` is deliberately not guarded by `_closing`.** It is the
  fallback a failed automatic update lands on, and by then `_closing` is already set; guarding it
  would leave a user whose install failed with a dead window.
- **`UpdateWindow` always exits the app through the injected `close_app_callback`**, on both the
  "Exit and Update" (`webbrowser.open()`) route and the "Update and Restart" route, because an
  installer that finds the executable still running hangs trying to close it. The second route
  and its progress bar appear only when a `start_install_callback` is passed.
- **`PatchNotesWindow` takes a string, not a path**, and is not just `FileEditorWindow(editable=False)`.
  The notes are frequently the concatenated sections of several releases, so they are no file on
  disk; `FileEditorWindow` also carries a save callback, renders monospace, and has nowhere for
  the heading. The box is disabled after the insert; the font is the display font, since these
  are prose rather than aligned columns.

## GUI tests never open a window

Each `_build_window()` helper opens a `with` stack patching `tk.Toplevel.__init__`, the window's
own `title`/`configure`/`_center_over_parent`, and every widget class at its point of use
(`patch("fishbowl_common.gui.UpdateWindow.tk.Button", side_effect=_distinct_widget)`), where
`_distinct_widget` returns a fresh `MagicMock()` per widget so each is independently assertable.
That is what lets the whole suite run on `ubuntu-latest` with no display and no `python3-tk`.

`tests/gui/UpdateWindow_tests.py` is the richest fixture — mirror it rather than inventing a new
pattern. The general test conventions live in `.claude/rules/tests.md`.
