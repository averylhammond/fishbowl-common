# Changelog

All notable changes to `fishbowl-common` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

A version here reaches a consuming app only when that app moves its pin (see
[Setup](README.md#setup)), so an entry below describes what an app *would* get by moving to
that tag — not what it already has.

Headings are `## [X.Y.Z] - YYYY-MM-DD`, and that format is load-bearing: the release
workflow refuses to publish a tag with no matching `## [X.Y.Z]` heading in this file.

## [Unreleased]

### Changed

- The coverage gate is now 90% rather than 80%, matching both consuming apps, and the
  coverage workflow now runs on pushes to `main` as well as pull requests. Without the push
  run Codecov held no main-branch baseline, so the README badge never refreshed and the PR
  coverage comment had nothing to compare against. The Codecov upload also runs when the gate
  fails, which is when that comment is most worth reading.
  ([#11](https://github.com/averylhammond/fishbowl-common/issues/11))
- `SettingsRepository`'s SQL is now executed by tests rather than only asserted as text. Every
  existing test mocked `sqlite3.connect` and compared the statements to literal strings, so the
  suite would have passed against a wrong schema. Four tests over a real temporary database now
  pin the settings table's columns, the save-then-read round trip, and that saving an existing
  key updates its row instead of adding a second one.
  ([#11](https://github.com/averylhammond/fishbowl-common/issues/11))

### Added

- The package now ships a `py.typed` marker, so the annotations both halves already carried
  are published rather than discarded at the package boundary. Until now a type checker
  running in a consuming app treated every shared name as `Any`, which made checking a
  `fishbowl_common` call impossible: the annotations existed and no tool was allowed to read
  them. ([#9](https://github.com/averylhammond/fishbowl-common/issues/9))
- `fishbowl_common.__version__` reports the installed version, so an app can name which shared
  build it is running alongside its own. It is a literal in the new
  `fishbowl_common/_version.py`, which `pyproject.toml` reads via `[tool.setuptools.dynamic]`
  — the version still lives in exactly one place, but that place is now source rather than
  packaging metadata, so it survives into the PyInstaller onefile builds both apps ship.
  ([#9](https://github.com/averylhammond/fishbowl-common/issues/9))
- The package is now licensed (MIT, with a `LICENSE` file) and its metadata is complete: a
  readme, an author, project URLs and classifiers. `pip show fishbowl-common` reports a
  license and a homepage rather than nothing.
  ([#9](https://github.com/averylhammond/fishbowl-common/issues/9))
- `UpdateChecker` now records why a check failed in `last_error`, as one of the
  `CHECK_ERROR_RATE_LIMITED` / `CHECK_ERROR_HTTP` / `CHECK_ERROR_NETWORK` /
  `CHECK_ERROR_RESPONSE` values exported from the package root. The check still fails
  silently by returning `None`, so nothing an app already does changes; a caller that wants to
  tell a throttled check apart from an offline machine can now read it. `UpdateCoordinator`
  does, and a manual check that was rate limited no longer sends the user after their internet
  connection. ([#6](https://github.com/averylhammond/fishbowl-common/issues/6))

### Fixed

- `UpdateDownloader` now sends the same `User-Agent` on both of its requests — the checksums
  fetch and the installer download — instead of going out as `Python-urllib`, which the
  filtering proxies these apps are deployed behind routinely refuse. Those two requests move
  the bytes that land on a customer's disk, so the check identifying itself while they did not
  was the more dangerous half of the gap. Both also catch `urllib.error.HTTPError` ahead of
  `URLError` now, and record why they failed in `last_error` — one of `DOWNLOAD_ERROR_HTTP`,
  `DOWNLOAD_ERROR_NETWORK`, `DOWNLOAD_ERROR_IO`, `DOWNLOAD_ERROR_NO_DIGEST`,
  `DOWNLOAD_ERROR_SIZE` or `DOWNLOAD_ERROR_DIGEST`. `UpdateCoordinator` copies that reason to
  `last_download_error` before the outcome crosses to the GUI thread, since it builds the
  downloader itself and never hands it out.
  ([#6](https://github.com/averylhammond/fishbowl-common/issues/6))
- `UpdateChecker` now sends a `User-Agent`, `Accept: application/vnd.github+json` and
  `X-GitHub-Api-Version` with its request, which GitHub's API documents as required and can
  refuse a request without. It also catches `urllib.error.HTTPError` ahead of `URLError`, so a
  403 from the unauthenticated rate limit (60 requests/hour/IP — one shared budget for a whole
  office, and both apps check on every launch) is no longer indistinguishable from being
  offline. ([#6](https://github.com/averylhammond/fishbowl-common/issues/6))
- `SettingsRepository.initialize_database()` now reports an `OSError` from creating the
  data directory through `report_error` instead of letting it escape the `sqlite3.Error`
  handler. A read-only or permission-denied data directory crashed the consuming app at
  startup, before its display existed.
  ([#4](https://github.com/averylhammond/fishbowl-common/issues/4))
- `SettingsRepository` now closes its SQLite connection after every call. `sqlite3`'s
  connection context manager only commits or rolls back, so `initialize_database()`,
  `get_all_settings()` and `save_setting()` each left a connection open until the garbage
  collector finalized it — and on Windows kept the database file locked longer than
  expected. Both apps write a setting on every preference change and every checkbox
  toggle. ([#3](https://github.com/averylhammond/fishbowl-common/issues/3))

## [1.3.0] - 2026-08-21

### Added

- `PatchNotes`, a reader for the changelog file an app ships beside its executable. Given
  the running version and the version the user last launched, it returns the `## X.Y.Z`
  sections between them, newest first — so a user who skipped a release still sees what it
  changed — and an empty string when the file is missing, unreadable or has nothing to say.
  ([#22](https://github.com/averylhammond/fishbowl-common/issues/22))
- `PatchNotesWindow`, the themed window showing those notes: a heading naming the app and
  version, the notes in a read-only box, and a Close button. Together with `PatchNotes` this
  is the shared half of "show what changed on the first launch after an update"; the
  settings key, the version stamp and the packaged notes file are each app's own.
  ([#22](https://github.com/averylhammond/fishbowl-common/issues/22))
- `version_utils`, holding the `parse_version()` and `compare_versions()` that
  `UpdateChecker` and `PatchNotes` now share.
  ([#22](https://github.com/averylhammond/fishbowl-common/issues/22))
- A release workflow (`.github/workflows/release.yml`): a pushed `v*` tag is verified
  against `pyproject.toml`'s version and against this changelog, the unit tests are run,
  an sdist and wheel are built and smoke-installed, and a GitHub Release is published with
  both attached. ([#10](https://github.com/averylhammond/fishbowl-common/issues/10))
- This changelog, backfilled across every tag released so far.
  ([#10](https://github.com/averylhammond/fishbowl-common/issues/10))
- `CLAUDE.md`, documenting the package's architecture, testing and release conventions.
  ([#12](https://github.com/averylhammond/fishbowl-common/issues/12))

### Fixed

- The update check no longer mistakes a pre-release tag for a failed check. `v2.2.0-rc1`
  raised while the version was being parsed, which `check_for_update()` caught and returned
  as `None` — shown to the user as "Update Check Failed — check your internet connection"
  after a perfectly successful request. Unequal segment counts are also zero-padded now, so
  a `1.2` release is no longer offered as an update to a user already running `1.2.0`.
  ([#5](https://github.com/averylhammond/fishbowl-common/issues/5))

### Changed

- **Not breaking, but worth noting at a call site.** `UpdateChecker._parse_version()` is
  gone; the comparison lives in `version_utils` as `parse_version()` and
  `compare_versions()`. Nothing outside the class called the private method, so no consumer
  has to change.

## [1.2.1] - 2026-08-18

### Fixed

- `UpdateInstaller` now strips the frozen application's `_PYI_*` variables from the
  environment it hands the installer, so the application the installer relaunches starts
  normally. Since PyInstaller 6.22.1 an app that starts with those set takes itself for a
  worker sub-process and requires its parent to be the same executable — it is Setup, so it
  refused to start at all after an otherwise successful in-place upgrade.
  ([#20](https://github.com/averylhammond/fishbowl-common/issues/20))

## [1.2.0] - 2026-08-18

### Added

- The in-app update download and install. `UpdateDownloader` fetches a release asset in
  chunks with progress, verifying it against the published size and SHA-256 before anything
  is executed; `UpdateInstaller` starts the verified Inno Setup installer silently and
  detached with `/RELAUNCH=1`; `UpdateCoordinator` drives both off the GUI thread; and
  `UpdateWindow` gains an "Update and Restart" button with a themed progress bar. A release
  missing the installer or its checksums, or a platform that is not Windows, still gets the
  manual download. ([#16](https://github.com/averylhammond/fishbowl-common/issues/16))

### Changed

- **Breaking.** `show_update_available()` takes a second `start_install` argument. Both apps
  implement that method, so both had to move their pin together — the precedent case for a
  change to this package landing as three PRs rather than one.

## [1.1.0] - 2026-08-18

### Added

- `UpdateCoordinator`, which owns the whole update-check flow both apps had duplicated: the
  daemon thread, the `UpdateChecker` call, the hop back onto the GUI thread via `after()`,
  and the decision to open the update window versus reporting an up-to-date or failed check
  only when the user asked for one. Its display collaborator is typed as a `Protocol`, so it
  stays in the headless half of the package.
  ([#14](https://github.com/averylhammond/fishbowl-common/issues/14))

## [1.0.1] - 2026-08-18

### Added

- `fishbowl_common.gui`, behind a `[gui]` extra: `ThemedSubwindow`, `MessageWindow`,
  `AboutWindow`, `FileEditorWindow`, `UpdateWindow`, `Tooltip`, `color_theme` and
  `font_settings`, lifted from the two apps. The extra installs no packages — tkinter ships
  with CPython — and marks intent: the top-level `fishbowl_common` must stay importable with
  no Tcl/Tk present, which `tests/test_headless_import.py` now enforces.
  ([#13](https://github.com/averylhammond/fishbowl-common/issues/13))
- A code-coverage workflow gating pull requests at 80%.
  ([#1](https://github.com/averylhammond/fishbowl-common/pull/1))

### Changed

- The README was standardized against the format the other Fishbowl repos use.
  ([#2](https://github.com/averylhammond/fishbowl-common/pull/2))

*No `1.0.0` was ever tagged: the version went straight from `0.1.0` to `1.0.1`.*

## [0.1.0] - 2026-07-22

### Added

- Initial release: `ArgumentProvider`, `SettingsRepository` and `UpdateChecker`, their unit
  tests, and the unit-test workflow.

[Unreleased]: https://github.com/averylhammond/fishbowl-common/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/averylhammond/fishbowl-common/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/averylhammond/fishbowl-common/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/averylhammond/fishbowl-common/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/averylhammond/fishbowl-common/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/averylhammond/fishbowl-common/compare/v0.1.0...v1.0.1
[0.1.0]: https://github.com/averylhammond/fishbowl-common/releases/tag/v0.1.0
