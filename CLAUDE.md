# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

> **Keep the guidance current.** Whenever you change the package's architecture — add/remove/
> rename a class or module, move a responsibility between the two halves, change a public
> signature, or alter the build/test/release workflow — update **this file or the matching
> `.claude/rules/` file** in the same change. Treat that as part of the definition of done for
> any structural change, not an afterthought.

## Project Overview

`fishbowl-common` (import name `fishbowl_common`) is the shared infrastructure and GUI package
behind the two Fishbowl desktop tools,
[FishbowlInvoiceTool](https://github.com/averylhammond/FishbowlInvoiceTool) and
[FishbowlInventoryTool](https://github.com/averylhammond/FishbowlInventoryTool). It ships no
application of its own: everything here is machinery those two apps would otherwise duplicate —
CLI argument parsing, settings persistence, the whole update check/download/install flow, and
the themed tkinter windows.

The package is split in two halves. `fishbowl_common` itself is **headless** and imports nothing
but the standard library, so an app can use it from an integration test running on a machine
with no display. `fishbowl_common.gui` holds the tkinter windows and is declared behind a `[gui]`
extra. Neither half is optional-by-accident — see the split rule under Key conventions.

Consumers take this package as a **pinned git tag**, never as a path or a submodule, so a change
here is invisible to an app until that app moves its pin. **A change that alters a public
signature is not one PR but three** — here, then `FishbowlInvoiceTool`, then
`FishbowlInventoryTool`. Run `/move-the-pin` before starting one.

## Setup

- Python 3.11 (`requires-python = ">=3.11"`; CI pins `3.11.9`).
- Virtual env: `python -m venv venv`, then `source venv/Scripts/activate` (Windows) or
  `source venv/bin/activate` (Linux/Mac).
- Install for development: `pip install -e ".[dev,gui]"`. The `dev` extra is
  `pytest`/`pytest-cov`; the `gui` extra is **empty** and adds no requirements (tkinter ships
  with CPython) — it exists to mark intent.
- `pyproject.toml` is the whole of the packaging, pytest and coverage configuration. There is no
  `setup.py`, `setup.cfg`, `.coveragerc` or `pytest.ini`, unlike the two apps.

## Common Commands

- Run all unit tests: `pytest`
- Run a single test file: `pytest tests/test_UpdateChecker.py`
- Run a single test:
  `pytest tests/test_UpdateChecker.py::test_check_for_update_returns_none_on_network_error`
- Run with coverage: `pytest --cov=fishbowl_common --cov-report=term-missing`
- Byte-compile sanity check:
  `python -m py_compile fishbowl_common/*.py fishbowl_common/gui/*.py tests/*.py tests/gui/*.py`

## Architecture

Everything public is re-exported from the two package roots, and consumers import from those
names rather than from the individual modules. **Keep a new public name listed in both the
import block and `__all__`.**

`fishbowl_common/__init__.py` never touches `fishbowl_common.gui`, so `import fishbowl_common`
does not pull in tkinter.

### Headless half — `fishbowl_common/`

| Module | Role |
| --- | --- |
| `ArgumentProvider` | Parses `--integration-test` into `integration_test_mode` so an app can run headless with no GUI popups. Reads `sys.argv` directly and cannot yet be handed an `argv` (#8). |
| `SettingsRepository` | SQLite key/value store for user settings. **Stores only text.** |
| `version_utils` | `parse_version()` / `compare_versions()`, two module-level functions. **Neither ever raises.** |
| `PatchNotes` | Reads a shipped changelog and returns every section in a version *range*, newest first. |
| `UpdateChecker` | Queries the GitHub releases API; returns an `UpdateCheckResult` or `None`, and names the failure in `last_error`. |
| `UpdateDownloader` | Streams an asset and verifies size + SHA-256 before the caller executes it. |
| `UpdateInstaller` | Starts a downloaded Inno Setup installer silently and detached (Windows only). |
| `UpdateCoordinator` | The whole update feature as one object, and the only update class an app constructs. |
| `UpdateDisplay` | A `typing.Protocol` (in `UpdateCoordinator.py`) — what keeps the coordinator headless. |

### GUI half — `fishbowl_common/gui/`

The themed tkinter layer both apps share: `color_theme`, `font_settings`, `ThemedSubwindow`,
`MessageWindow`, `AboutWindow`, `FileEditorWindow`, `PatchNotesWindow`, `UpdateWindow`,
`Tooltip`. Every window snapshots the active theme and font when it opens, so it stays styled
consistently with the main window behind it.

## Key conventions

- **Every class is application-agnostic, and every app-specific value arrives by constructor
  injection.** No module-level default path, no environment variable, no import of a consumer's
  `constants`, no application name or repo baked in anywhere. The failure this prevents is quiet:
  a default that encodes one app's choice is invisible in this repo's tests and silently wrong in
  the other app. When a new value is needed, add a parameter — and where a default is genuinely
  generic, make it generic by construction rather than by picking one app's value.
- **The headless half must never import tkinter.** `FishbowlInventoryTool`'s integration job runs
  on `ubuntu-latest` with no display. Four things enforce it, all load-bearing:
  `fishbowl_common/__init__.py` never touches `gui`; `UpdateCoordinator` types its collaborator
  as `UpdateDisplay(Protocol)` rather than importing a window; the empty `[gui]` extra marks the
  split in the consumers' pins; and `tests/test_headless_import.py` fails the build if it stops
  being true. **A new headless module that needs to talk to a window gets a Protocol, not an
  import.**
- **`report_error` is the callback pattern for a failure the user should see.**
  `report_error: Callable[[str, str], None] = lambda *_: None`, invoked as `(title, message)`,
  never re-raising. `SettingsRepository` is the only class carrying one today. **The update
  classes and `PatchNotes` deliberately have none** — they return `None`/`False`/`""` silently,
  and a silent startup check on an offline machine is the designed behavior, not an oversight.
  `UpdateChecker.last_error` is not a hole in that rule: it *records* why the last check failed
  for a caller that asks, and reports nothing to anyone on its own.
- **Zero runtime dependencies.** `dependencies = []`, and every import in both halves is stdlib.
  `README.md:11-12` advertises this, and both apps ship as PyInstaller onefile builds where each
  added dependency is payload the customer downloads. **Taking a runtime dependency is a
  deliberate decision, not a convenience.** The case that tested it was #5, where
  `packaging.version.Version` would have fixed the version comparison correctly at the cost of
  the claim; stdlib-only won, and `version_utils` is the hand-rolled result. If `packaging` ever
  wins that argument, the README claim, `pyproject.toml` and both apps' installs move with it —
  it is not a local edit.
- **Anything both apps need belongs here, not in an app's `source/gui/`.** Both apps' `CLAUDE.md`
  files carry the mirror of this rule ("do not re-add a local copy — fix or extend them in
  `fishbowl-common` and bump the pin"). A helper duplicated across the two apps is a candidate
  for this package; one only the invoice tool wants is not.
- Keep comments concise: a comment should explain only what the immediately adjacent code does.
  Do not document another module's behavior from a call site.

## Unit Testing

Tests live in `tests/`, mirroring the package: `tests/test_<ClassName>.py` per source module,
and `tests/gui/` for `fishbowl_common/gui/`. `tests/__init__.py` and `tests/gui/__init__.py` are
empty but load-bearing; there is deliberately **no `conftest.py`**.

Every unit test exercises exactly **one** class or function, with all collaborators mocked. Never
let a unit test touch the real network, a real GUI, or the real filesystem — with exactly one
carve-out: `SettingsRepository`'s SQL is proved against a real `tmp_path` database, because the
SQL genuinely is the thing under test. See `.claude/rules/settings-repository.md`; do not read it
as license for a second exception.

**Before writing a test, open the reference implementation and mirror it** —
`tests/test_UpdateCoordinator.py` for a class with injected collaborators,
`tests/gui/test_UpdateWindow.py` for a window. Reading either loads the full conventions from
`.claude/rules/tests.md`.

## CI

Three `ubuntu-latest` workflows. Two run on `pull_request` to `main` and `workflow_dispatch`,
`code-coverage.yml` also on `push` to `main`; the third runs only on a pushed `v*` tag.

| Workflow | What it runs |
| --- | --- |
| `unit-tests.yml` | bare `pytest` |
| `code-coverage.yml` | `pytest --cov` with `--cov-fail-under=90`, then `codecov/codecov-action@v5` |
| `release.yml` | two `::error::` gates, `pytest`, `python -m build`, a wheel smoke-install, then `gh release create` |

Coverage omits `color_theme.py` and `font_settings.py` as inert styling data; **every other
measured module is at 100%**, so the gate is headroom, not a target to climb toward.

## Git Workflow (when working on a GitHub issue)

- Check out the base branch (usually `main`) and pull (`git checkout main && git pull`) before
  branching, so work starts from the current tip rather than a stale local copy.
- Name the branch with the issue number so GitHub links it:
  `git checkout -b <issue-number>-<short-description>` (e.g. `14-update-coordinator`).
- One imperative-mood subject line, ending `(closes #N)` or carrying a `(vX.Y.Z)` marker when the
  change bumps the version.
- Merge through a PR. If the change alters a public signature, it is step 1 of three — run
  `/move-the-pin`.
- Cutting a release: run `/cut-a-release`.

## Where the rest of the guidance lives

Detail that only matters for part of the codebase lives in `.claude/rules/`, loaded automatically
when a matching file is opened, and in `.claude/skills/`, loaded when invoked.

| File | Loads when you touch | Carries |
| --- | --- | --- |
| `rules/update-classes.md` | `Update*.py` | The `UpdateInstaller` switch rationale, the download verification contract, coordinator threading |
| `rules/gui.md` | `gui/**` | Window catalogue, `Tooltip` `add="+"`, the widget-patching test stack |
| `rules/tests.md` | `tests/**` | Fixtures, patch targets, FIRST, banner and docstring conventions |
| `rules/ci-and-packaging.md` | `.github/workflows/**`, `pyproject.toml` | Workflow internals, release gates, coverage gaps |
| `rules/versioning.md` | `version_utils.py`, `PatchNotes.py` | The never-raises contract, pre-release limitation, notes-range semantics |
| `rules/settings-repository.md` | `SettingsRepository.py` | Text-only table, `report_error` mechanics, known defects |
| `/cut-a-release` | — | Bump, changelog, tag, and the two gates that fail a release |
| `/move-the-pin` | — | The three-repo rollout for a public-signature change |
| `/add-a-module` | — | Checklist for landing a new class or public name |
