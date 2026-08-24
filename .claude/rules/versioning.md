---
paths:
  - "fishbowl_common/version_utils.py"
  - "fishbowl_common/PatchNotes.py"
  - "tests/test_version_utils.py"
  - "tests/test_PatchNotes.py"
---

# Version parsing and patch notes

## `version_utils`

Two module-level functions rather than a class, the only such module in the headless half. The
three behaviors callers depend on:

- `parse_version()` stops at the first segment with no leading digits, **so a pre-release tag
  parses instead of raising**.
- `compare_versions()` zero-pads to equal length, **so `1.2` and `1.2.0` are the same version**.
- **Neither ever raises**: an unparseable version yields `()`, and each caller turns that into its
  own quiet outcome.
- `UpdateChecker` and `PatchNotes` both use it, which is why it is a module of its own rather than
  a method on either — a pure-logic reader should not import the module that does network I/O. Do
  not reimplement a comparison in a caller or sanitize version strings in a consumer.
- The accepted limitation is that a pre-release sorts **equal** to its final release
  (`2.2.0-rc1` == `2.2.0`). Ordering those correctly is PEP 440's job and would mean taking
  `packaging`, which the zero-runtime-dependency rule in `CLAUDE.md` rules out.

## `PatchNotes`

It reads a changelog file an app **ships in its release payload** (next to `USER_GUIDE.txt`)
rather than a release body from GitHub, so the first launch after an update needs no network —
these run on shop-floor machines.

- **It returns a range, not one version's notes**, because a user who skips a release and updates
  straight past it must still be told what that release changed.
- `last_seen_version=None` means *no lower bound*, not "show nothing". Deciding that a fresh
  install should be shown nothing belongs to the consuming app, which is the only side that can
  tell a fresh install from an upgrade.
- **It fails silently**, like the update classes and unlike `SettingsRepository`: a missing,
  unreadable or unparseable file returns `""` and takes no `report_error`. A cosmetic feature must
  never be able to stop the app from starting.
- The file is read per call rather than in `__init__`, so constructing one cannot fail. The
  heading pattern tolerates a leading `v`, a `[...]` wrapper and a trailing date, and each section
  keeps its heading line so a multi-version result says which notes belong to which release.
