# fishbowl-common

[![Unit Tests](https://github.com/averylhammond/fishbowl-common/actions/workflows/unit-tests.yml/badge.svg)](https://github.com/averylhammond/fishbowl-common/actions/workflows/unit-tests.yml)
[![Code Coverage](https://github.com/averylhammond/fishbowl-common/actions/workflows/code-coverage.yml/badge.svg)](https://github.com/averylhammond/fishbowl-common/actions/workflows/code-coverage.yml)
[![codecov](https://codecov.io/gh/averylhammond/fishbowl-common/branch/main/graph/badge.svg)](https://codecov.io/gh/averylhammond/fishbowl-common)

Shared infrastructure classes for the Fishbowl desktop tools
([FishbowlInvoiceTool](https://github.com/averylhammond/FishbowlInvoiceTool),
[FishbowlInventoryTool](https://github.com/averylhammond/FishbowlInventoryTool)). These
classes are application-agnostic — anything app-specific (paths, versions, repo names)
is injected by the consumer.

## Contents

- **`ArgumentProvider`** — parses the `--integration-test` CLI flag so an app can run
  headless (no GUI popups) during automated testing.
- **`SettingsRepository`** — a SQLite key/value store for user settings (theme, font,
  etc.) that survive between runs. The database path is injected by the caller.
- **`UpdateChecker`** — queries the GitHub releases API for a newer version and compares
  it against the running version. The current version and `owner/repo` are injected by
  the caller; the check fails silently (returns `None`) on any network/parse error.

## Install

Add a pinned git dependency to the consuming app's requirements:

```
fishbowl-common @ git+ssh://git@github.com/averylhammond/fishbowl-common.git@v0.1.0
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

## Development

```bash
python -m venv venv
source venv/Scripts/activate   # Windows; use venv/bin/activate on Linux/Mac
pip install -e ".[dev]"
pytest tests/*
```

### Continuous integration

Every pull request to `main` must pass two checks (see the badges above):

- **Unit Tests** — the full `pytest` suite.
- **Code Coverage** — the suite run under coverage, which fails if total coverage
  drops below **80%**.

Reproduce the coverage check locally with:

```bash
pytest --cov=fishbowl_common --cov-report=term-missing --cov-fail-under=80
```
