# fishbowl-common

[![Unit Tests](https://github.com/averylhammond/fishbowl-common/actions/workflows/unit-tests.yml/badge.svg?branch=main)](https://github.com/averylhammond/fishbowl-common/actions/workflows/unit-tests.yml)
[![Code Coverage](https://github.com/averylhammond/fishbowl-common/actions/workflows/code-coverage.yml/badge.svg?branch=main)](https://github.com/averylhammond/fishbowl-common/actions/workflows/code-coverage.yml)
[![codecov](https://codecov.io/gh/averylhammond/fishbowl-common/branch/main/graph/badge.svg)](https://codecov.io/gh/averylhammond/fishbowl-common)

Shared infrastructure classes for the Fishbowl desktop tools
([FishbowlInvoiceTool](https://github.com/averylhammond/FishbowlInvoiceTool),
[FishbowlInventoryTool](https://github.com/averylhammond/FishbowlInventoryTool)). These
classes are application-agnostic — anything app-specific (paths, versions, repo names)
is injected by the consumer. The package has no runtime dependencies beyond the standard
library.

## Contents

- **`ArgumentProvider`** — parses the `--integration-test` CLI flag so an app can run
  headless (no GUI popups) during automated testing.
- **`SettingsRepository`** — a SQLite key/value store for user settings (theme, font,
  etc.) that survive between runs. The database path is injected by the caller.
- **`UpdateChecker`** — queries the GitHub releases API for a newer version and compares
  it against the running version. The current version and `owner/repo` are injected by
  the caller; the check fails silently (returns `None`) on any network/parse error.

## Setup

Add a pinned git dependency to the consuming app's requirements:

```
fishbowl-common @ git+https://github.com/averylhammond/fishbowl-common.git@v0.1.0
```

To work on the package itself (Python 3.11):

```bash
python -m venv venv
source venv/Scripts/activate   # Windows; use venv/bin/activate on Linux/Mac
pip install -e ".[dev]"
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

## Testing

```bash
pytest tests/*                                                        # unit tests
pytest --cov=fishbowl_common --cov-report=term-missing tests/*        # with a coverage table
```

Test files use the `*_tests.py` suffix; `pyproject.toml` widens pytest discovery to match
them, so a bare `pytest` works here too.

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
  Uses `ArgumentProvider`.
