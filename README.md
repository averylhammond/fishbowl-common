# fishbowl-common

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
