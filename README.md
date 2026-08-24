# fishbowl-common

[![Unit Tests](https://github.com/averylhammond/fishbowl-common/actions/workflows/unit-tests.yml/badge.svg?branch=main)](https://github.com/averylhammond/fishbowl-common/actions/workflows/unit-tests.yml)
[![Code Coverage](https://github.com/averylhammond/fishbowl-common/actions/workflows/code-coverage.yml/badge.svg?branch=main)](https://github.com/averylhammond/fishbowl-common/actions/workflows/code-coverage.yml)
[![codecov](https://codecov.io/gh/averylhammond/fishbowl-common/branch/main/graph/badge.svg)](https://codecov.io/gh/averylhammond/fishbowl-common)
[![Release](https://github.com/averylhammond/fishbowl-common/actions/workflows/release.yml/badge.svg)](https://github.com/averylhammond/fishbowl-common/actions/workflows/release.yml)

Shared infrastructure and GUI classes for the Fishbowl desktop tools
([FishbowlInvoiceTool](https://github.com/averylhammond/FishbowlInvoiceTool),
[FishbowlInventoryTool](https://github.com/averylhammond/FishbowlInventoryTool)). These
classes are application-agnostic — anything app-specific (paths, versions, repo names,
the application's own name) is injected by the consumer. The package has no runtime
dependencies beyond the standard library.

The package is split in two halves. `fishbowl_common` itself is headless: it imports
nothing but the standard library, so an app can use it from an integration test running
on a machine with no display. `fishbowl_common.gui` holds the tkinter windows and is
declared behind a [`[gui]` extra](#setup).

## Contents

- **`ArgumentProvider`** — parses the `--integration-test` CLI flag so an app can run
  headless (no GUI popups) during automated testing.
- **`SettingsRepository`** — a SQLite key/value store for user settings (theme, font,
  etc.) that survive between runs. The database path is injected by the caller.
- **`PatchNotes`** — reads the changelog file an app ships beside its executable and
  returns the `## X.Y.Z` sections between the version the user last launched and the one
  they are running now, newest first, so the app can show them what an update changed.
  Reading a bundled file rather than a release body means the first launch after an update
  needs no network. It returns a range rather than one version's notes, so a user who
  skipped a release still sees it, and it fails silently: a missing or unparseable file
  returns an empty string.
- **`version_utils`** — `parse_version()` and `compare_versions()`, the semantic version
  comparison `UpdateChecker` and `PatchNotes` share. Neither raises: a pre-release tag
  parses to its numeric version rather than failing, and both sides are zero-padded before
  they are compared, so `1.2` and `1.2.0` are the same version.
- **`UpdateChecker`** — queries the GitHub releases API for a newer version and compares
  it against the running version, also surfacing the release's installer and checksums
  assets. The current version, `owner/repo` and the installer's `asset_pattern` are
  injected by the caller; the check fails silently (returns `None`) on any network/parse
  error.
- **`UpdateDownloader`** — downloads a release asset in chunks, reporting progress as it
  goes, and verifies it against the size and SHA-256 the release published before the
  caller ever executes it. A failed download, a wrong size or a wrong digest all return
  `None`, and the partial file is deleted.
- **`UpdateInstaller`** — starts a downloaded Inno Setup installer silently and detached,
  passing `/RELAUNCH=1` so the application comes back after the upgrade. Detaching is
  what lets the installer outlive the application it is replacing, whose executable
  Windows keeps file-locked while it runs. Two of its switches and one of its habits
  exist because a frozen application is not an ordinary parent process:
  `/FORCECLOSEAPPLICATIONS` alongside `/CLOSEAPPLICATIONS`, because Restart Manager
  closes an application by posting to its window and a PyInstaller onefile bootloader
  owns none — without it Setup waits out its timeout and `/SUPPRESSMSGBOXES` turns the
  resulting prompt into an Abort, rolling the upgrade back silently. And the installer is
  started with the bootloader's own `_PYI_*` variables stripped from the environment,
  since it passes that environment on to the application it relaunches, which since
  PyInstaller 6.22.1 refuses to start when it sees them (it takes them to mean it is a
  worker sub-process and requires its parent to be the same executable).

  A consuming application's `installer.iss` still needs its own half of this — the
  `/RELAUNCH=1` gate, and `CloseApplications=force` so an upgrade launched by an older
  build is covered too.
- **`UpdateCoordinator`** — runs an `UpdateChecker` on a daemon thread and turns its
  outcome into the right user-facing response: the update window whenever a newer
  release exists, and an up-to-date/failure popup only when the user asked for the
  check. When the release publishes an installer this platform can run, it also owns the
  download-and-install flow — again off the GUI thread, with progress and the outcome
  marshalled back through the window's `after()`. The window it presents through is typed
  as a `Protocol`, so this stays in the headless half even though the collaborator is a
  tkinter window.

### `fishbowl_common.gui`

The themed tkinter layer both apps share. Every window snapshots the active theme and
font when it opens, so it stays styled consistently with the main window behind it.

- **`color_theme`** — the `Theme` dataclass, the four built-in themes (`DARK`, `LIGHT`,
  `OCEAN`, `FOREST`), `ALL_THEMES`, `THEME_BY_NAME`, and the named color palette.
- **`font_settings`** — the selectable font families and sizes, plus the defaults and
  the monospace family used where character alignment matters.
- **`ThemedSubwindow`** — base class for the transient secondary windows below: attaches
  to the parent, snapshots theme/font, sets the title and background, and centers itself
  over the parent.
- **`MessageWindow`** — the themed OK-button popup an app shows in place of
  `tkinter.messagebox`.
- **`AboutWindow`** — a read-only window showing the application name and version, both
  injected by the caller.
- **`FileEditorWindow`** — views or edits one text file in a monospace box; an `editable`
  flag toggles the Save button.
- **`PatchNotesWindow`** — shows what changed in the version now running: a heading
  naming the app and version, the notes in a read-only scrolling box, and a Close button.
  The notes are passed in as a string rather than a path, since they are often several
  releases' sections concatenated.
- **`UpdateWindow`** — announces a newer release and offers the ways to get it: "Update
  and Restart" (with a themed progress bar) when the caller passes an install callback,
  and always "Exit and Update", which opens the release's download page. Either way it
  closes the application through an injected callback, so an installer is not blocked by
  the running executable; a failed automatic update falls back to the download page.
- **`Tooltip`** — hover text for a single widget, shown after a short delay so a pointer
  merely crossing the widget never flashes a tip.

## Setup

Add a pinned git dependency to the consuming app's requirements:

```
fishbowl-common[gui] @ git+https://github.com/averylhammond/fishbowl-common.git@v1.2.1
```

Drop the `[gui]` to install only the headless half. The extra pulls in no packages —
tkinter ships with CPython — so it is a declaration of intent rather than a dependency:
`import fishbowl_common` must keep working on a machine with no Tcl/Tk, and
`tests/test_headless_import.py` fails the build if that ever stops being true.

To work on the package itself (Python 3.11):

```bash
python -m venv venv
source venv/Scripts/activate   # Windows; use venv/bin/activate on Linux/Mac
pip install -e ".[dev,gui]"
```

## Usage

```python
from pathlib import Path
from fishbowl_common import ArgumentProvider, SettingsRepository, UpdateChecker

args = ArgumentProvider()
if args.integration_test_mode:
    ...

settings = SettingsRepository(db_path=Path("data") / "settings.db")
settings.save_setting("theme", "Ocean")

result = UpdateChecker(
    current_version="1.2.3", repo="averylhammond/FishbowlInvoiceTool"
).check_for_update()
if result and result.update_available:
    ...
```

Most consumers want the whole update flow rather than the bare fetch, which is what
`UpdateCoordinator` wraps. It never blocks the caller and never touches the display off
the GUI thread:

```python
from fishbowl_common import UpdateCoordinator

coordinator = UpdateCoordinator(
    current_version="1.2.3",
    repo="averylhammond/FishbowlInvoiceTool",
    display=self,  # any object with after()/show_update_available()/show_popup()
    asset_pattern="FishbowlInvoiceTool_Setup.exe",  # omit for the manual download only
)

coordinator.start()               # silent startup check
coordinator.start(manual=True)    # Help -> Check for Updates; always reports an outcome
```

Passing an `asset_pattern` is what turns on the in-app "Update and Restart" button. It
needs two things from the release: the installer the pattern names, and a
`SHA256SUMS.txt` asset listing that installer's digest — the download is verified against
it before anything is executed. A release missing either, or a platform that is not
Windows, quietly leaves the window offering the manual download instead, so nothing
breaks on an older release.

The GUI half is imported separately, so a headless code path never loads tkinter:

```python
from fishbowl_common.gui import AboutWindow, DARK, DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE

AboutWindow(
    parent=self,
    title="About",
    app_name="Fishbowl Invoice Tool",
    version="1.2.3",
    theme=DARK,
    font_family=DEFAULT_FONT_FAMILY,
    font_size=DEFAULT_FONT_SIZE,
)
```

## Testing

```bash
pytest                                                        # unit tests
pytest --cov=fishbowl_common --cov-report=term-missing        # with a coverage table
```

`pyproject.toml` points pytest at `tests/`, so a bare `pytest` finds everything —
including the GUI tests under `tests/gui/`. Those never open a window: each one patches
`tk.Toplevel.__init__` and every widget class, so the suite runs on a machine with no
display. `color_theme` and `font_settings` are excluded from coverage as inert data.

## Continuous integration

The first two run on pull requests to `main` and on manual dispatch, and Code Coverage also
runs on pushes to `main` so Codecov keeps a main-branch baseline for PR comparisons; the
third runs only when a version tag is pushed.

| Workflow | What it checks |
| --- | --- |
| [Unit Tests](.github/workflows/unit-tests.yml) | The full `pytest` suite on `ubuntu-latest`. |
| [Code Coverage](.github/workflows/code-coverage.yml) | `pytest --cov=fishbowl_common --cov-report=xml --cov-report=term --cov-fail-under=90`, uploaded to Codecov. |
| [Release](.github/workflows/release.yml) | On a pushed `v*` tag: the tag against `pyproject.toml`, the tag against [`CHANGELOG.md`](CHANGELOG.md), the test suite, and that the built wheel installs and imports. |

## Releases

The package version lives in `pyproject.toml` and is published by tag. Consumers pin a
tag in their requirements (see [Setup](#setup)), so bumping the version here has no
effect on an app until that app's pin is moved to the new tag.
[`CHANGELOG.md`](CHANGELOG.md) records what each tag changed, which is what makes moving a
pin a decision rather than an act of faith.

Pushing a `vX.Y.Z` tag runs the release workflow, which publishes a GitHub Release with an
sdist and a wheel attached — so an app can pin a release asset instead of a git ref if it
prefers. It refuses to publish unless the tag matches `pyproject.toml`'s version and
`CHANGELOG.md` documents that version, so a release can never ship a distribution whose
number disagrees with the tag naming it, or one nothing records.

Cutting a release:

```bash
# Bump `version` in pyproject.toml and move CHANGELOG.md's [Unreleased] section under a
# `## [X.Y.Z] - YYYY-MM-DD` heading, then merge that PR. Then, from an up-to-date main:
git checkout main && git pull
git tag vX.Y.Z && git push origin vX.Y.Z
```

Tags `v0.1.0` through `v1.2.1` predate this workflow and have no Release behind them. They
remain valid pins — a git ref is all a pin resolves — and the changelog covers them.

## Related projects

- [FishbowlInvoiceTool](https://github.com/averylhammond/FishbowlInvoiceTool) — parses
  Fishbowl invoice PDFs and computes cost breakdowns. Uses the whole package.
- [FishbowlInventoryTool](https://github.com/averylhammond/FishbowlInventoryTool) —
  parses Fishbowl inventory availability and turnover report PDFs into an Excel report.
  Uses the whole package.
