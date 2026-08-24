---
paths:
  - "tests/**"
---

# Unit testing conventions

Tests live in `tests/`, mirroring the package: `tests/test_<ClassName>.py` per source module,
and `tests/gui/` for `fishbowl_common/gui/`. `tests/__init__.py` and `tests/gui/__init__.py` are
empty but **load-bearing** — with them present, pytest's prepend import mode puts the repo root
on `sys.path`, which is what makes `from fishbowl_common import ...` resolve. There is
deliberately **no `conftest.py`**; all pytest and coverage configuration lives in
`pyproject.toml`.

`tests/test_UpdateCoordinator.py` (a class with injected collaborators) and
`tests/gui/test_UpdateWindow.py` (the richest widget-patching fixture) are the two reference
implementations — mirror them rather than inventing new patterns.

## Test one object in isolation

Every unit test exercises exactly **one** class or function, with all collaborators mocked, so a
failure points unambiguously at the unit under test. Never let a unit test touch the real
network, a real GUI, or the real filesystem — the single carve-out is described at the bottom of
this file.

- **Fixtures return a `types.SimpleNamespace`** bundling the object under test with its mocks
  (`coordinator.coordinator` / `coordinator.display`), so a test reaches both without re-deriving
  either.
- **Module-level private constants supply the inputs** — `_TEST_REPO`, `_INSTALLER_NAME`,
  `_ASSET_URL`, `_PAYLOAD_SHA256 = hashlib.sha256(_PAYLOAD).hexdigest()` — rather than literals
  repeated per test.
- **Patch at the point of use, with the fully-qualified target**:
  `@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")`,
  `patch("fishbowl_common.SettingsRepository.sqlite3.connect")` — never the definition site, and
  never the whole module (`urllib`, `sqlite3`) when an `except` clause names an exception from it,
  since replacing the module makes that clause reference a non-exception and raise `TypeError`
  while handling the error.
- **Mock the `UpdateDisplay` collaborator as `MagicMock(spec=UpdateDisplay)`**, so a call to
  anything outside the Protocol fails the test rather than passing silently.
- **GUI tests never open a window** — the `_build_window()` patching stack is described in
  `.claude/rules/gui.md`.
- **`tests/test_headless_import.py` is an enforcement test, not a unit test.** It blocks
  `tkinter` through `builtins.__import__`, evicts the cached `tkinter*`/`fishbowl_common*`
  entries from `sys.modules`, then asserts `fishbowl_common` imports cleanly and
  `fishbowl_common.gui` raises `ImportError`. Do not delete or weaken it while refactoring
  imports — it is the only thing that catches the headless split being broken.

## FIRST, as it binds here

The generic principles are assumed. The three that constrain this suite specifically:

- **Fast** — no real network or GUI, and no filesystem I/O beyond the `tmp_path` database in
  `test_SettingsRepository.py`. The whole run stays under a second, and that is a budget, not an
  observation.
- **Repeatable** — `git status` must show no new artifacts after a run.
- **Timely** — a new branch or utility function gets its test in the same change.

## Naming and structure

- Test files are named `test_<ClassName>.py`, matching pytest's default discovery.
- Flat module-level `test_<method>_<behavior>` functions — no test classes.
- Group tests under the `###`-bordered banners used throughout the file:
  `<Class> -> Test Fixture`, `<Class> -> Test Helpers`, then one `Tests <Class> -> <method>()`
  section per method, matching the banner style the source modules themselves use.
- Give every test and helper a docstring describing what it verifies, with an `Args:` block
  documenting every mock/fixture parameter.

## The one carve-out from "no real I/O"

`tests/test_SettingsRepository.py` is the only file mixing mocked and real tests, and each half
earns its place (#11):

- the **mocked** tests (`settings_repo`, patching `sqlite3.connect`) cover the `report_error`
  branches, the `OSError` from `mkdir`, and `connection.close()` on every path — failures a real
  database will not readily produce;
- the **real** tests (`real_settings_repo`, a `tmp_path` database with nothing patched) are the
  only ones that execute the SQL, so they are what catches a wrong schema. The literal-string
  assertions on their own cannot: rename a column in both the source and the expected string and
  the mocked half stays green.

This is not a precedent for a second exception. It holds because the SQL genuinely *is* the unit
under test, and it stays cheap and hermetic: `tmp_path` sits outside the repo, so `git status` is
still clean after a run. Detail in `.claude/rules/settings-repository.md`.
