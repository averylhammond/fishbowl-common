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
- **Every method opens its own connection and closes it, via a doubled `with`:**
  `with closing(sqlite3.connect(self.db_path)) as connection, connection:`. Both managers are
  load-bearing and neither replaces the other — `closing()` closes the connection, while the
  connection's own context manager only commits or rolls back. Dropping the wrapper leaks a
  connection on every call, which is what #3 was. A new method touching the database uses the
  same pairing.

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

## The two halves of `tests/test_SettingsRepository.py`

This is the one file in the suite that mixes mocked and real database tests, and the split is
deliberate (#11).

- **The mocked half** patches `fishbowl_common.SettingsRepository.sqlite3.connect` and asserts the
  SQL as literal strings. It covers what a real database will not readily produce: each `except`
  branch reporting through `report_error`, the `OSError` from `mkdir`, and `connection.close()`
  being called on every path including a failed write.
- **The real half** uses the `real_settings_repo(tmp_path)` fixture with nothing patched, and is
  the only thing that executes the SQL. It pins the schema via `PRAGMA table_info(settings)`, the
  save-then-read round trip, and that the upsert leaves **one** row rather than two.

**A change to the schema or to any SQL in this class gets a `tmp_path` test that executes it**,
not another literal-string assertion. The literal assertions alone cannot catch a wrong schema:
rename a column in both the source and the expected string and the mocked half stays green, which
is precisely the hole #11 closed.
