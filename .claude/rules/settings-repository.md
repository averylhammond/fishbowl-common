---
paths:
  - "fishbowl_common/SettingsRepository.py"
  - "tests/test_SettingsRepository.py"
---

# `SettingsRepository`

A SQLite key/value store for user settings. `__init__` calls `initialize_database()` directly,
which is why the `report_error` default matters (below).

- **The table stores only text**, which is a constraint the consumers depend on — an app
  persisting a boolean compares the stored string against `str(True)` on the way back rather than
  calling `bool()` on it, since `bool("False")` is `True`.
- One known defect lives here: **a connection is leaked on every call (#3)**. Fix it here rather
  than working around it at a call site.

## The `report_error` pattern

This is the only class carrying one today:
`report_error: Callable[[str, str], None] = lambda *_: None`, stored on the instance and invoked
as `(title, message)` from inside one `except` block per method, never re-raising.

- `initialize_database()` catches `(sqlite3.Error, OSError)` rather than `sqlite3.Error` alone,
  since its `mkdir` fails with the latter (#4).
- **The no-op default is what lets `initialize_database()` run from `__init__` before any display
  exists** — an error there falls to the no-op, and only later reads and writes reach the app's
  popup.
- A new class that can fail in a way the user must act on takes the same parameter, with the same
  no-op default. The update classes deliberately have none; see
  `.claude/rules/update-classes.md`.

## The test gap

`tests/test_SettingsRepository.py` patches `sqlite3.connect` and asserts the SQL as literal
strings, so **the tests would still pass if the schema were wrong** — nothing ever executes it. A
`tmp_path` round-trip covering save-then-read and the upsert is tracked as #11, and is the one
place a real (temporary) file is the right call.
