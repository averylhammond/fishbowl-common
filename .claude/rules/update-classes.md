---
paths:
  - "fishbowl_common/Update*.py"
  - "tests/test_Update*.py"
---

# The update flow

Five objects make up the update feature. `UpdateCoordinator` is the only one a consuming app
constructs; the rest are its collaborators.

## `UpdateChecker`

- `DEFAULT_CHECKSUMS_NAME = "SHA256SUMS.txt"` is the asset name an app's release pipeline must
  publish for an in-place install to be offered. Renaming it here silently downgrades both apps
  to the manual download rather than failing anything.
- **Every request carries `REQUEST_HEADERS`** — `User-Agent`, `Accept` and
  `X-GitHub-Api-Version` — which is why `check_for_update()` builds a `urllib.request.Request`
  rather than handing `urlopen()` a bare URL. GitHub documents the User-Agent as required and
  can refuse a request without one; the other two pin the response to the schema this module
  parses. Do not drop back to a bare URL for brevity.
- **`urllib.error.HTTPError` is caught ahead of `URLError`, and the order is the fix** (#6).
  It subclasses `URLError`, so the broad handler used to swallow a 403 from the unauthenticated
  rate limit — 60 requests/hour/IP, one budget shared by an office, and both apps check on every
  launch — and return the same bare `None` as an unplugged cable. `_is_rate_limited()` will not
  read a 403 alone as a rate limit, because GitHub answers an ordinary refusal with the same
  status; it wants an exhausted `X-RateLimit-Remaining`, a `Retry-After`, or a 429.
- **`last_error` carries one of the `CHECK_ERROR_*` values after a failed check**, and is
  cleared at the top of every call. It is the *only* thing separating those failures for a
  caller, and `UpdateCoordinator` reads it to word a manual check's popup — see the
  no-`report_error` rule below, which it does not break.
- **The version comparison is not its own.** `check_for_update()` calls `compare_versions()`
  from `version_utils`; the private `_parse_version()` it used to carry was extracted there when
  `PatchNotes` came to need the identical comparison (#22), and fixed while it moved (#5). Do
  not reimplement a comparison here or sanitize version strings in a consumer.

## `UpdateDownloader`

- **Both requests send `REQUEST_HEADERS`, and it is the `User-Agent` alone** — no `Accept`, no
  API version, because these fetch a file from the asset host rather than the API (#6). The
  default `Python-urllib` is what a filtering proxy on an office network refuses, and these are
  the two requests that put bytes on a customer's disk.
- **`last_error` carries one of the `DOWNLOAD_ERROR_*` values**, set by both `fetch_expected_sha256()`
  and `download()` and cleared at the top of each. `DOWNLOAD_ERROR_IO` deliberately covers both a
  disk failure and a socket error raised outside `URLError`: both arrive as a bare `OSError`, and
  separating them would mean splitting the read/write loop for a distinction no message needs.
  `DOWNLOAD_ERROR_DIGEST` is the one worth treating as more than bad luck.
- **Every failure path goes through `_discard_and_fail()`**, so no path can record a reason while
  leaving something runnable on disk.

`download()` verifies the result against the published size and SHA-256 **before the caller ever
executes it** — the caller is about to run this file as an installer, so the check is the only
thing standing between a corrupted or substituted download and code execution. A failed download,
a wrong size or a wrong digest all return `None` **and delete the partial file**, so a failure can
never leave something runnable on disk.

## `UpdateInstaller`

Starts a downloaded Inno Setup installer silently and detached, so it outlives the application
whose executable it is replacing (Windows keeps that file locked while it runs).

**Every one of its switches and habits is load-bearing, and each was found by a failed real
upgrade in `FishbowlInvoiceTool` (its issue #106, releases 4.1.0 through 4.1.5) rather than by
reasoning** — `README.md:34-50` carries the full account. Do not weaken any of them:

- `SILENT_ARGS` carries `/FORCECLOSEAPPLICATIONS` **alongside** `/CLOSEAPPLICATIONS`, because
  Restart Manager closes an application by posting to its window and a PyInstaller onefile
  bootloader owns none. Without it Setup waits out its timeout, and `/SUPPRESSMSGBOXES` turns the
  resulting prompt into an Abort — the upgrade rolls back silently and the user is left on the
  old version with no error shown.
- `RELAUNCH_ARG = "/RELAUNCH=1"` is what brings the application back afterwards. The consuming
  app's `installer.iss` gates its post-install run on that parameter, so a hand-run silent
  install still starts nothing.
- `_clean_environment()` strips the `PYINSTALLER_ENV_PREFIX` (`_PYI_`) variables and
  `PYINSTALLER_LEGACY_ENV_VARS` (`_MEIPASS2`) from what the installer is started with, because
  the installer passes its environment on to the application it relaunches — which, since
  PyInstaller 6.22.1, refuses to start when it sees them.

## `UpdateCoordinator`

The whole update feature as one object, and the only one of these an app constructs.

- **Every network call runs on a `daemon=True` thread and comes back through
  `display.after(0, ...)`.** Tk is not thread-safe; touching a widget from the worker is the bug
  this shape exists to prevent. A new background step follows the same pattern.
- **`last_download_error` is how a download's reason reaches an app** (#6). The coordinator builds
  its `UpdateDownloader` inside `_run_install` and never hands it out, so copying `last_error` onto
  itself before `display.after(0, on_finished, started)` is the only way out. Reporting it *through*
  the display would mean widening `FinishedCallback` or the `UpdateDisplay` Protocol — both
  pin-moving changes that break two apps with no import to warn you.
- **The failure message is chosen from `CHECK_FAILED_MESSAGES`, keyed by the checker's
  `last_error`** (#6). A rate-limited check earns its own wording because nothing is wrong with
  the machine and the same check succeeds later untouched; "check your internet connection" sends
  the user after a problem they do not have. `_run_check` reads `last_error` on the worker thread
  and hands it to `_handle_result`, so the GUI thread never reaches back into the checker.
- **`_handle_result` pops "no updates"/"check failed" only when `manual=True`.** It opens the
  update window whenever a newer release exists, but a startup check must never interrupt a launch
  just because the machine is offline. This is a design decision, not an oversight — see the
  no-`report_error` rule below.

## `UpdateDisplay` (also in `UpdateCoordinator.py`)

**This Protocol is what keeps the coordinator in the headless half** even though the object passed
in is a Tk window; importing a concrete window class here would drag tkinter into
`fishbowl_common`. Both apps' displays satisfy it structurally, with no base class and no
registration — so **adding a method to it breaks both apps with no import to warn you**, and is a
pin-moving change.

## These classes deliberately carry no `report_error`

`UpdateChecker`, `UpdateDownloader` and `UpdateInstaller` return `None`/`False` silently, and
`UpdateCoordinator` decides whether the user hears about it at all (only on a manual check). Do
not "improve" them by adding a reporter: a silent startup check on an offline machine is the
designed behavior, not an oversight.

`UpdateChecker.last_error` is deliberately *not* that reporter, and #6 is where the line was
drawn. It tells no one anything: it records why the last call failed and waits to be asked, so
the startup check stays as silent as it ever was while the coordinator can still say something
truthful on a manual one. A new "why did it fail" signal in these classes takes that shape —
recorded state a caller reads — rather than a callback that speaks.
