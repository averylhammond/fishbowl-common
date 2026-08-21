# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Keep this file current.** Whenever you change the package's architecture —
> add/remove/rename a class or module, move a responsibility between the two halves,
> change a public signature, or alter the build/test/release workflow — update the
> relevant section of this file in the same change. Treat `CLAUDE.md` as part of the
> definition of done for any structural change, not an afterthought.

## Project Overview

`fishbowl-common` (import name `fishbowl_common`) is the shared infrastructure and GUI
package behind the two Fishbowl desktop tools,
[FishbowlInvoiceTool](https://github.com/averylhammond/FishbowlInvoiceTool) and
[FishbowlInventoryTool](https://github.com/averylhammond/FishbowlInventoryTool). It ships
no application of its own: everything here is machinery those two apps would otherwise
duplicate — CLI argument parsing, settings persistence, the whole update
check/download/install flow, and the themed tkinter windows.

The package is split in two halves. `fishbowl_common` itself is **headless** and imports
nothing but the standard library, so an app can use it from an integration test running on
a machine with no display. `fishbowl_common.gui` holds the tkinter windows and is declared
behind a `[gui]` extra. Neither half is optional-by-accident: see the split rule under
[Key conventions](#key-conventions).

Consumers take this package as a **pinned git tag**, never as a path or a submodule, so a
change here is invisible to an app until that app moves its pin. That is the single fact
that shapes how work lands here; see
[Consuming Apps and the Pin](#consuming-apps-and-the-pin).

## Setup

- Python 3.11 (`requires-python = ">=3.11"`; CI pins `3.11.9`).
- Virtual env: `python -m venv venv`, then `source venv/Scripts/activate` (Windows) or
  `source venv/bin/activate` (Linux/Mac).
- Install for development: `pip install -e ".[dev,gui]"`. The `dev` extra is
  `pytest`/`pytest-cov`; the `gui` extra is **empty** and adds no requirements (tkinter
  ships with CPython) — it exists to mark intent.
- There is no `setup.py` and no `setup.cfg`. `pyproject.toml` is the whole of the
  packaging, pytest and coverage configuration; there is no `.coveragerc` and no
  `pytest.ini`, unlike the two apps.

## Common Commands

- Run all unit tests: `pytest` — a bare invocation works because
  `[tool.pytest.ini_options]` sets `python_files = ["*_tests.py"]` and
  `testpaths = ["tests"]`. **Do not remove that block**: this project names its test files
  with the `_tests.py` suffix, which pytest's default `test_*.py` pattern does not match,
  so without it a bare `pytest` collects nothing and CI passes vacuously. (It is also why
  the two apps, which have no such block, invoke `pytest tests/*`.)
- Run a single test file: `pytest tests/UpdateChecker_tests.py`
- Run a single test:
  `pytest tests/UpdateChecker_tests.py::test_check_for_update_returns_none_on_network_error`
- Run with coverage: `pytest --cov=fishbowl_common --cov-report=term-missing`
- Byte-compile sanity check:
  `python -m py_compile fishbowl_common/*.py fishbowl_common/gui/*.py tests/*.py tests/gui/*.py`

## Consuming Apps and the Pin

The version lives in exactly one place, `version` in `pyproject.toml`, and is published by
tag. Tags to date: `v1.2.1`, `v1.2.0`, `v1.1.0`, `v1.0.1`, `v0.1.0`.

Both apps carry the byte-identical pin at `requirements/release.txt:1`:

```
fishbowl-common[gui] @ git+https://github.com/averylhammond/fishbowl-common.git@v1.2.1
```

**A change here reaches an app only when that app moves its pin.** That cuts both ways:
work can land on `main` here without breaking anything downstream, and a fix is not
actually delivered until two other repos are edited. So a change that alters a public
signature is not one PR but three, in order:

1. Here: make the change, bump `version` in `pyproject.toml`, add the matching
   `## [X.Y.Z]` section to `CHANGELOG.md`, merge, push the matching `vX.Y.Z` tag. The
   changelog entry lands **with** the bump, not after it — the release workflow refuses to
   publish a tag the changelog does not document.
2. `FishbowlInvoiceTool`: move the pin, adapt the call sites, merge.
3. `FishbowlInventoryTool`: the same.

The precedent is `v1.2.0`, which changed `show_update_available()` to take a second
`start_install` argument — a method both apps implement, so both had to move together.
Plan for that shape of work rather than discovering it at step 2.

Pushing the tag is what runs `.github/workflows/release.yml`, and two `::error::` gates
there make the pin trustworthy: the tag must equal `pyproject.toml`'s `version`, and
`CHANGELOG.md` must carry a `## [X.Y.Z]` section for it. So the changelog is the answer to
"what do I get by moving the pin", and it cannot fall behind the version without failing
the release. The five tags predating that workflow (`v0.1.0` through `v1.2.1`) were pushed
by hand and have no GitHub Release behind them; they are backfilled in `CHANGELOG.md` and
still work as pins, since a git ref is all a pin needs.

One gap in this pipeline is still tracked rather than fixed: the packaging metadata has no
`py.typed`, `LICENSE` or `__version__` — the annotations are written throughout and then
discarded at the package boundary (#9).

## Architecture

Everything public is re-exported from the two package roots, and consumers import from
those names rather than from the individual modules. Keep a new public name listed in both
the import block and `__all__`.

- **`fishbowl_common/__init__.py`** — re-exports `ArgumentProvider`, `ReleaseAsset`,
  `SettingsRepository`, `UpdateChecker`, `UpdateCheckResult`, `UpdateCoordinator`,
  `UpdateDisplay`, `UpdateDownloader` and `UpdateInstaller`. It never touches
  `fishbowl_common.gui`, so `import fishbowl_common` does not pull in tkinter.
- **`ArgumentProvider`** (`fishbowl_common/ArgumentProvider.py`) — parses the
  `--integration-test` flag into `integration_test_mode` so an app can run headless with
  no GUI popups. `__init__(description="Fishbowl desktop application")` takes only a
  generic `--help` label; it reads `sys.argv` directly and cannot yet be handed an `argv`
  (#8).
- **`SettingsRepository`** (`fishbowl_common/SettingsRepository.py`) —
  `__init__(db_path: Path, report_error=lambda *_: None)`, a SQLite key/value store for
  user settings. `__init__` calls `initialize_database()`, which `mkdir`s the parent and
  runs `CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)`;
  `get_all_settings()` returns `{}` on error; `save_setting(key, value)` upserts via
  `ON CONFLICT(key) DO UPDATE SET value=excluded.value`. **The table stores only text**,
  which is a constraint the consumers depend on — an app persisting a boolean compares the
  stored string against `str(True)` on the way back rather than calling `bool()` on it,
  since `bool("False")` is `True`.
  - Two known defects live here: a connection is leaked on every call (#3), and `mkdir`'s
    `OSError` escapes the `sqlite3.Error` handler (#4). Fix them here rather than working
    around either at a call site.
- **`UpdateChecker`** (`fishbowl_common/UpdateChecker.py`) —
  `__init__(current_version, repo, asset_pattern=None, checksums_name=DEFAULT_CHECKSUMS_NAME)`,
  building `https://api.github.com/repos/{repo}/releases/latest`. `check_for_update()`
  returns an `UpdateCheckResult` or `None`; `_find_asset()` fnmatches a release's assets
  against `asset_pattern`. Two inert value objects come with it: `ReleaseAsset` (`name`,
  `download_url`, `size`) and `UpdateCheckResult` (`update_available`, `latest_version`,
  `release_url`, `installer_asset`, `checksums_asset`).
  - `DEFAULT_CHECKSUMS_NAME = "SHA256SUMS.txt"` is the asset name an app's release
    pipeline must publish for an in-place install to be offered. Renaming it here silently
    downgrades both apps to the manual download rather than failing anything.
  - **`_parse_version()` is hand-rolled and known-broken in two ways** (#5): a non-numeric
    segment (`v2.2.0-rc1`) raises, which `check_for_update()` catches and turns into
    `None` — indistinguishable to the user from being offline — and unequal segment counts
    compare element-wise, so `1.2` sorts below `1.2.0`. Fix it here rather than sanitizing
    version strings in a consumer.
- **`UpdateDownloader`** (`fishbowl_common/UpdateDownloader.py`) — stateless, no
  collaborators, no `__init__`. `fetch_expected_sha256()` reads the digest out of the
  checksums asset; `download()` streams the asset in `CHUNK_SIZE` pieces, reporting
  progress, and verifies the result against the published size and SHA-256 **before the
  caller ever executes it**. A failed download, a wrong size or a wrong digest all return
  `None` and delete the partial file. `default_destination()` places the download in a
  fresh `tempfile.mkdtemp()` directory.
- **`UpdateInstaller`** (`fishbowl_common/UpdateInstaller.py`) — starts a downloaded Inno
  Setup installer silently and detached, so it outlives the application whose executable it
  is replacing (Windows keeps that file locked while it runs). `is_supported()` is
  `sys.platform == "win32"`. **Every one of its switches and habits is load-bearing, and
  each was found by a failed real upgrade in `FishbowlInvoiceTool` (its issue #106,
  releases 4.1.0 through 4.1.5) rather than by reasoning** — `README.md:34-50` carries the
  full account. Do not weaken any of them:
  - `SILENT_ARGS` carries `/FORCECLOSEAPPLICATIONS` **alongside** `/CLOSEAPPLICATIONS`,
    because Restart Manager closes an application by posting to its window and a
    PyInstaller onefile bootloader owns none. Without it Setup waits out its timeout, and
    `/SUPPRESSMSGBOXES` turns the resulting prompt into an Abort — the upgrade rolls back
    silently and the user is left on the old version with no error shown.
  - `RELAUNCH_ARG = "/RELAUNCH=1"` is what brings the application back afterwards. The
    consuming app's `installer.iss` gates its post-install run on that parameter, so a
    hand-run silent install still starts nothing.
  - `_clean_environment()` strips the `PYINSTALLER_ENV_PREFIX` (`_PYI_`) variables and
    `PYINSTALLER_LEGACY_ENV_VARS` (`_MEIPASS2`) from what the installer is started with,
    because the installer passes its environment on to the application it relaunches —
    which, since PyInstaller 6.22.1, refuses to start when it sees them.
- **`UpdateCoordinator`** (`fishbowl_common/UpdateCoordinator.py`) — the whole update
  feature as one object, and the only one of the update classes an app constructs.
  `__init__(current_version, repo, display, asset_pattern=None)`. `start(manual=False)`
  runs `_run_check` on a `daemon=True` thread and marshals the outcome back with
  `display.after(0, self._handle_result, ...)`; `_handle_result` opens the update window
  whenever a newer release exists but pops "no updates"/"check failed" **only when
  `manual`**, so a startup check never interrupts a launch just because the user is
  offline. `_can_install()` requires an installer asset, a checksums asset and
  `UpdateInstaller.is_supported()`; when all three hold, `start_install()` runs the
  download-and-install on another daemon thread and reports progress and the outcome back
  through the display's `after()`.
- **`UpdateDisplay`** (`fishbowl_common/UpdateCoordinator.py`) — a `typing.Protocol` with
  `after()`, `show_update_available()` and `show_popup()`. **This is what keeps the
  coordinator in the headless half** even though the object passed in is a Tk window;
  importing a concrete window class here would drag tkinter into `fishbowl_common`. Both
  apps' displays satisfy it structurally, with no base class and no registration.

### `fishbowl_common.gui`

The themed tkinter layer both apps share, all of it re-exported from
`fishbowl_common/gui/__init__.py`. Every window snapshots the active theme and font when
it opens, so it stays styled consistently with the main window behind it.

- **`color_theme`** — the `Theme` dataclass (`name`, `bg_main`, `bg_entry`, `fg_text`,
  `accent`, `button_bg`, `button_fg`, `label_fg`), the named palette, the four built-in
  themes `DARK`/`LIGHT`/`OCEAN`/`FOREST`, `ALL_THEMES` and `THEME_BY_NAME`. Only `RED` is
  re-exported from the palette — it is the one bare color a consumer applies directly (the
  Exit button).
- **`font_settings`** — `DEFAULT_FONT_FAMILY`, `FONT_FAMILIES`, `DEFAULT_FONT_SIZE`,
  `FONT_SIZES`, and `MONOSPACE_FONT_FAMILY` for the places character alignment matters.
- **`ThemedSubwindow`** — the `tk.Toplevel` base for every window below: attaches to the
  parent, snapshots theme/font, sets the title and background, and centers itself over the
  parent.
- **`MessageWindow`** — the themed OK-button popup an app shows in place of
  `tkinter.messagebox`.
- **`AboutWindow`** — shows `app_name` and `version`, **both injected**, which is the whole
  reason a window this app-specific can live here at all.
- **`FileEditorWindow`** — views or edits one text file in a monospace box; `editable`
  toggles the Save button and `save_callback` is guarded, so a read-only open needs none.
- **`UpdateWindow`** — announces a newer release. It always offers "Exit and Update"
  (`webbrowser.open()` on the release page) and additionally offers "Update and Restart"
  with a progress bar when a `start_install_callback` is passed. Either route exits the
  application through the injected `close_app_callback`, because an installer that finds
  the executable still running hangs trying to close it.
- **`Tooltip`** — hover text for a single widget, shown after `SHOW_DELAY_MS` (500ms) so a
  pointer merely crossing the widget never flashes a tip. Not a `ThemedSubwindow`: it
  builds its own borderless `Toplevel` on hover. `update_style()` restyles it in place.

### Key conventions

- **Every class is application-agnostic, and every app-specific value arrives by
  constructor injection.** No module-level default path, no environment variable, no
  import of a consumer's `constants`, no application name or repo baked in anywhere.
  `SettingsRepository` is handed its `db_path`; `UpdateChecker`/`UpdateCoordinator` their
  `current_version`, `repo` and `asset_pattern`; `AboutWindow` its `app_name` and
  `version`. This is the rule the package exists to hold, and the failure it prevents is
  quiet: a default that encodes one app's choice is invisible in this repo's tests and
  silently wrong in the other app. When a new value is needed, add a parameter — and where
  a default is genuinely generic (`description` on `ArgumentProvider`, `checksums_name` on
  `UpdateChecker`), make it generic by construction rather than by picking one app's value.
- **The headless half must never import tkinter.** `FishbowlInventoryTool`'s integration
  job runs on `ubuntu-latest` with no display, so an app's headless path must be able to
  import `fishbowl_common` on a machine with no Tcl/Tk. Four things enforce that, and all
  four are load-bearing: `fishbowl_common/__init__.py` never touches `gui`;
  `UpdateCoordinator` types its collaborator as `UpdateDisplay(Protocol)` rather than
  importing a window; the empty `[gui]` extra marks the split in the consumers' pins; and
  `tests/headless_import_tests.py` fails the build if it ever stops being true. A new
  headless module that needs to talk to a window gets a Protocol, not an import.
- **`report_error` is the callback pattern for a failure the user should see.**
  `SettingsRepository` is the only class carrying one today:
  `report_error: Callable[[str, str], None] = lambda *_: None`, stored on the instance and
  invoked as `(title, message)` from inside three `except sqlite3.Error` blocks, never
  re-raising. **The no-op default is what lets `initialize_database()` run from `__init__`
  before any display exists** — an error there falls to the no-op, and only later reads and
  writes reach the app's popup. A new class that can fail in a way the user must act on
  takes the same parameter, with the same no-op default.
  - **The update classes deliberately have none.** `UpdateChecker`, `UpdateDownloader` and
    `UpdateInstaller` return `None`/`False` silently, and `UpdateCoordinator` decides
    whether the user hears about it at all (only on a manual check). Do not "improve" them
    by adding a reporter: a silent startup check on an offline machine is the designed
    behavior, not an oversight.
- **Zero runtime dependencies.** `dependencies = []`, and every import in both halves is
  stdlib. `README.md:11-12` advertises this, and both apps ship as PyInstaller onefile
  builds where each added dependency is payload the customer downloads. **Taking a runtime
  dependency is a deliberate decision, not a convenience.** The live case is #5, where
  `packaging.version.Version` would fix `_parse_version()` correctly at the cost of the
  claim; the current stance is that stdlib-only holds and #5 is fixed with a hand-rolled
  parser. If `packaging` ever wins that argument, the README claim, `pyproject.toml` and
  both apps' installs move with it — it is not a local edit.
- **`Tooltip` binds with `add="+"`, and that flag is load-bearing downstream.**
  `FishbowlInventoryTool` attaches a tooltip to every column checkbutton, each of which
  already carries a `command` that persists that column's state. A binding without
  `add="+"` replaces it, silently breaking the checkbox rather than raising anything.
- **`UpdateWindow._send_to_release_page()` is deliberately not guarded by `_closing`.** It
  is the fallback a failed automatic update lands on, and by then `_closing` is already
  set; guarding it would leave a user whose install failed with a dead window.
- **Anything both apps need belongs here, not in an app's `source/gui/`.** Both apps'
  `CLAUDE.md` files carry the mirror of this rule ("do not re-add a local copy — fix or
  extend them in `fishbowl-common` and bump the pin"). A helper duplicated across the two
  apps is a candidate for this package; one only the invoice tool wants is not.
- Keep comments concise: a comment should explain only what the immediately adjacent code
  does. Do not document another module's behavior from a call site.

## Unit Testing

Tests live in `tests/`, mirroring the package: `tests/<ClassName>_tests.py` per source
module, and `tests/gui/` for `fishbowl_common/gui/`. `tests/__init__.py` and
`tests/gui/__init__.py` are empty but **load-bearing** — with them present, pytest's
prepend import mode puts the repo root on `sys.path`, which is what makes
`from fishbowl_common import ...` resolve. There is deliberately **no `conftest.py`**; all
pytest and coverage configuration lives in `pyproject.toml`.

`tests/UpdateCoordinator_tests.py` (a class with injected collaborators) and
`tests/gui/UpdateWindow_tests.py` (the richest widget-patching fixture) are the two
reference implementations — mirror them rather than inventing new patterns.

### Test one object in isolation

Every unit test exercises exactly **one** class or function, with all collaborators
mocked, so a failure points unambiguously at the unit under test. Never let a unit test
touch the real network, a real GUI, or the real filesystem.

- **Fixtures return a `types.SimpleNamespace`** bundling the object under test with its
  mocks (`coordinator.coordinator` / `coordinator.display`), so a test reaches both
  without re-deriving either.
- **Module-level private constants supply the inputs** — `_TEST_REPO`, `_INSTALLER_NAME`,
  `_ASSET_URL`, `_PAYLOAD_SHA256 = hashlib.sha256(_PAYLOAD).hexdigest()` — rather than
  literals repeated per test.
- **Patch at the point of use, with the fully-qualified target**:
  `@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")`,
  `patch("fishbowl_common.SettingsRepository.sqlite3.connect")` — never the definition
  site, and never the whole module (`urllib`, `sqlite3`) when an `except` clause names an
  exception from it, since replacing the module makes that clause reference a
  non-exception and raise `TypeError` while handling the error.
- **Mock the `UpdateDisplay` collaborator as `MagicMock(spec=UpdateDisplay)`**, so a call
  to anything outside the Protocol fails the test rather than passing silently.
- **GUI tests never open a window.** Each `_build_window()` helper opens a `with` stack
  patching `tk.Toplevel.__init__`, the window's own `title`/`configure`/
  `_center_over_parent`, and every widget class at its point of use
  (`patch("fishbowl_common.gui.UpdateWindow.tk.Button", side_effect=_distinct_widget)`),
  where `_distinct_widget` returns a fresh `MagicMock()` per widget so each is
  independently assertable. That is what lets the whole suite run on `ubuntu-latest` with
  no display and no `python3-tk`.
- **`tests/headless_import_tests.py` is an enforcement test, not a unit test.** It blocks
  `tkinter` through `builtins.__import__`, evicts the cached `tkinter*`/`fishbowl_common*`
  entries from `sys.modules`, then asserts `fishbowl_common` imports cleanly and
  `fishbowl_common.gui` raises `ImportError`. Do not delete or weaken it while refactoring
  imports — it is the only thing that catches the split being broken.

### Follow the FIRST principles

- **Fast** — no real network, GUI, or (today) filesystem I/O; the whole run stays under a
  second.
- **Independent** — no ordering dependencies or shared mutable state between tests.
- **Repeatable** — deterministic on every machine, and `git status` shows no new artifacts
  after a run.
- **Self-validating** — each test asserts a clear pass/fail.
- **Timely** — add or extend tests alongside any new branch or utility function, in the
  same change.

The one acknowledged gap: `tests/SettingsRepository_tests.py` patches `sqlite3.connect`
and asserts the SQL as literal strings, so **the tests would still pass if the schema were
wrong** — nothing ever executes it. A `tmp_path` round-trip covering save-then-read and the
upsert is tracked as #11, and is the one place a real (temporary) file is the right call,
since the thing under test genuinely is the SQL.

### Conventions

- Test files are named `<ClassName>_tests.py` (suffix, not the pytest-default `test_`
  prefix) — see the `[tool.pytest.ini_options]` note under Common Commands.
- Flat module-level `test_<method>_<behavior>` functions — no test classes.
- Group tests under the `###`-bordered banners used throughout the file:
  `<Class> -> Test Fixture`, `<Class> -> Test Helpers`, then one
  `Tests <Class> -> <method>()` section per method, matching the banner style the source
  modules themselves use.
- Give every test and helper a docstring describing what it verifies, with an `Args:`
  block documenting every mock/fixture parameter.

### CI

Three workflows. Two run on `pull_request` to `main` and `workflow_dispatch`; the third
runs only on a pushed `v*` tag. All three are `ubuntu-latest` with
`actions/setup-python@v5` at `3.11.9` and `pip install -e ".[dev,gui]"`.

| Workflow | What it runs |
| --- | --- |
| `.github/workflows/unit-tests.yml` | bare `pytest` |
| `.github/workflows/code-coverage.yml` | `pytest --cov=fishbowl_common --cov-report=xml --cov-report=term --cov-fail-under=80`, then `codecov/codecov-action@v5` (needs `CODECOV_TOKEN`; `fail_ci_if_error: false`, so a Codecov outage never masks the gate) |
| `.github/workflows/release.yml` | two `::error::` gates, `pytest`, `python -m build`, a wheel smoke-install, then `gh release create --generate-notes` with the sdist and wheel attached |

`release.yml` fires on a pushed `v*` tag and publishes the GitHub Release. Four things in it
are load-bearing:

- **The tag must equal `pyproject.toml`'s `version`**, read with `tomllib` (stdlib on 3.11,
  so the gate needs nothing installed). This is the apps' own check with the version source
  swapped, since there is no `constants.py` here.
- **`CHANGELOG.md` must carry a `## [X.Y.Z]` section for the tag**, which has no analog in
  the apps. That `grep` and the changelog's heading format are one contract: reformat the
  headings and the check silently matches nothing.
- **The built wheel is installed into a fresh venv and imported before publishing**, both
  halves of it. `[tool.setuptools]` lists the packaged subpackages explicitly, so a
  subpackage added to the tree but not to that list would otherwise ship a half-empty wheel.
  The step `cd`s out of the repo first — from the root, the working directory's own
  `fishbowl_common/` shadows the installed one and the import proves nothing.
- **`build` is installed in the workflow, not added to the `dev` extra**, the same call the
  apps make by keeping PyInstaller out of `requirements/`: it is release tooling, not
  something a developer needs to run the tests.

Running on `ubuntu-latest` is a **deliberate divergence** from the apps' release workflows,
which must be `windows-latest` for PyInstaller and Inno Setup's `ISCC.exe`. This package
publishes a platform-independent sdist and wheel, so it builds where the other two
workflows do. It also needs no repo secret — no submodule, no `CUSTOMER_DATA_PAT` — and
uses the automatic `GITHUB_TOKEN` for the release.

`[tool.coverage.run]` omits `color_theme.py` and `font_settings.py` as inert styling data.
**Every other measured module is at 100%**, so the gate is headroom rather than a target to
climb toward — a new module landing untested should fail the check, not quietly lower the
average.

Two divergences from the apps' equivalent workflows are **gaps, not decisions**, both
tracked in #11: the gate is **80 here against 90 in both apps**, and there is **no
`push: branches: [main]` trigger**, so Codecov records no main-branch baseline, the badge
never updates and PR coverage comments have nothing to compare against. Do not read either
as an intentional mirror of the apps' files, and do not fix one without the other.

## Git Workflow (when working on a GitHub issue)

- Check out the base branch (usually `main`) and pull (`git checkout main && git pull`)
  before branching, so work starts from the current tip rather than a stale local copy.
- Name the branch with the issue number so GitHub links it:
  `git checkout -b <issue-number>-<short-description>` (e.g. `14-update-coordinator`).
- One imperative-mood subject line, ending `(closes #N)` or carrying a `(vX.Y.Z)` marker
  when the change bumps the version.
- Merge through a PR. If the change alters a public signature, remember it is step 1 of
  three — see [Consuming Apps and the Pin](#consuming-apps-and-the-pin).
- Cutting a release is: bump `version` in `pyproject.toml`, move `CHANGELOG.md`'s
  `## [Unreleased]` content under a `## [X.Y.Z] - YYYY-MM-DD` heading, merge, then push the
  matching `vX.Y.Z` tag. The release workflow fails the push if either half is missing.
