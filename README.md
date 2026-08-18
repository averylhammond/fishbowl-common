# fishbowl-common

[![Unit Tests](https://github.com/averylhammond/fishbowl-common/actions/workflows/unit-tests.yml/badge.svg?branch=main)](https://github.com/averylhammond/fishbowl-common/actions/workflows/unit-tests.yml)
[![Code Coverage](https://github.com/averylhammond/fishbowl-common/actions/workflows/code-coverage.yml/badge.svg?branch=main)](https://github.com/averylhammond/fishbowl-common/actions/workflows/code-coverage.yml)
[![codecov](https://codecov.io/gh/averylhammond/fishbowl-common/branch/main/graph/badge.svg)](https://codecov.io/gh/averylhammond/fishbowl-common)

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
- **`UpdateChecker`** — queries the GitHub releases API for a newer version and compares
  it against the running version. The current version and `owner/repo` are injected by
  the caller; the check fails silently (returns `None`) on any network/parse error.
- **`UpdateCoordinator`** — runs an `UpdateChecker` on a daemon thread and turns its
  outcome into the right user-facing response: the update window whenever a newer
  release exists, and an up-to-date/failure popup only when the user asked for the
  check. The window it presents through is typed as a `Protocol`, so this stays in the
  headless half even though the collaborator is a tkinter window.

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
- **`UpdateWindow`** — announces a newer release and opens its download page, then closes
  the application through an injected callback so an installer is not blocked by the
  running executable.
- **`Tooltip`** — hover text for a single widget, shown after a short delay so a pointer
  merely crossing the widget never flashes a tip.

## Setup

Add a pinned git dependency to the consuming app's requirements:

```
fishbowl-common[gui] @ git+https://github.com/averylhammond/fishbowl-common.git@v1.1.0
```

Drop the `[gui]` to install only the headless half. The extra pulls in no packages —
tkinter ships with CPython — so it is a declaration of intent rather than a dependency:
`import fishbowl_common` must keep working on a machine with no Tcl/Tk, and
`tests/headless_import_tests.py` fails the build if that ever stops being true.

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
)

coordinator.start()               # silent startup check
coordinator.start(manual=True)    # Help -> Check for Updates; always reports an outcome
```

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

Test files use the `*_tests.py` suffix; `pyproject.toml` widens pytest discovery to match
them and points it at `tests/`, so a bare `pytest` finds everything — including the GUI
tests under `tests/gui/`. Those never open a window: each one patches
`tk.Toplevel.__init__` and every widget class, so the suite runs on a machine with no
display. `color_theme` and `font_settings` are excluded from coverage as inert data.

## Continuous integration

Both workflows run on pull requests to `main` and on manual dispatch.

| Workflow | What it checks |
| --- | --- |
| [Unit Tests](.github/workflows/unit-tests.yml) | The full `pytest` suite on `ubuntu-latest`. |
| [Code Coverage](.github/workflows/code-coverage.yml) | `pytest --cov=fishbowl_common --cov-report=xml --cov-report=term --cov-fail-under=80`, uploaded to Codecov. |

## Releases

The package version lives in `pyproject.toml` and is published by tag. Consumers pin a
tag in their requirements (see [Setup](#setup)), so bumping the version here has no
effect on an app until that app's pin is moved to the new tag.

## Related projects

- [FishbowlInvoiceTool](https://github.com/averylhammond/FishbowlInvoiceTool) — parses
  Fishbowl invoice PDFs and computes cost breakdowns. Uses all three classes.
- [FishbowlInventoryTool](https://github.com/averylhammond/FishbowlInventoryTool) —
  parses Fishbowl inventory availability and turnover report PDFs into an Excel report.
  Uses all three classes.
