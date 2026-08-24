---
paths:
  - ".github/workflows/**"
  - "pyproject.toml"
  - "fishbowl_common/_version.py"
---

# CI and packaging

## The three workflows

Two run on `pull_request` to `main` and `workflow_dispatch`, and `code-coverage.yml` also on
`push` to `main`; the third runs only on a pushed `v*` tag. All three are `ubuntu-latest` with
`actions/setup-python@v5` at `3.11.9` and `pip install -e ".[dev,gui]"`.

`code-coverage.yml` needs a `CODECOV_TOKEN` repo secret. Its triggers, its gate and the two
flags on the Codecov upload are all load-bearing — see Coverage below.

## `release.yml` — four load-bearing things

- **The tag must equal `fishbowl_common/_version.py`'s `__version__`**, imported directly. This
  is the apps' own check with the version source swapped: `_version.py` is this package's
  `constants.py:VERSION`. It reads the module rather than `pyproject.toml` because `version` there
  is `dynamic` — the `[project]` table carries no literal to read, and a `tomllib` lookup for one
  would raise `KeyError` and fail every release for the wrong reason.
- **`CHANGELOG.md` must carry a `## [X.Y.Z]` section for the tag**, which has no analog in the
  apps. That `grep` and the changelog's heading format are one contract: reformat the headings
  and the check silently matches nothing.
- **The built wheel is installed into a fresh venv and imported before publishing**, both halves
  of it, and then asserted on. `[tool.setuptools]` lists the packaged subpackages explicitly, so a
  subpackage added to the tree but not to that list would otherwise ship a half-empty wheel; the
  same is true of `py.typed`, which reaches the wheel only through
  `[tool.setuptools.package-data]` and whose absence is silent — a consuming app's type checker
  just goes back to seeing an untyped package. The step therefore checks the installed package
  reports the tagged version and contains its `py.typed` marker. It `cd`s out of the repo first —
  from the root, the working directory's own `fishbowl_common/` shadows the installed one and the
  import proves nothing.
- **`build` is installed in the workflow, not added to the `dev` extra**, the same call the apps
  make by keeping PyInstaller out of `requirements/`: it is release tooling, not something a
  developer needs to run the tests.

Running on `ubuntu-latest` is a **deliberate divergence** from the apps' release workflows, which
must be `windows-latest` for PyInstaller and Inno Setup's `ISCC.exe`. This package publishes a
platform-independent sdist and wheel, so it builds where the other two workflows do. It also needs
no repo secret — no submodule, no `CUSTOMER_DATA_PAT` — and uses the automatic `GITHUB_TOKEN` for
the release.

## Coverage

`[tool.coverage.run]` omits `color_theme.py` and `font_settings.py` as inert styling data.
**Every other measured module is at 100%**, so the gate is headroom rather than a target to climb
toward — a new module landing untested should fail the check, not quietly lower the average.

The gate is **90, matching both apps** (#11). It was 80 here until the shared package — the piece
with the most consumers and the widest blast radius — stopped holding the loosest gate of the
three repos. Do not lower it to accommodate a new module.

`code-coverage.yml` triggers on **`push` to `main` as well as `pull_request`** (#11). The push run
is what gives Codecov a main-branch baseline: without it the badge never updates and the PR
coverage comment has nothing to diff against. Removing that trigger breaks the PR comment, not
just the badge.

The Codecov upload carries **both `if: always()` and `fail_ci_if_error: false`**, which sound
redundant and are not. `if: always()` runs the upload even when the pytest step failed the gate —
which is exactly when the PR coverage comment is worth reading. `fail_ci_if_error: false` keeps a
Codecov outage from failing the job for an unrelated reason and masking the gate's own verdict.

## Packaging metadata

Closed in #9, and each piece is load-bearing in a way that is easy to undo by accident:

- **`py.typed`** ships only because `[tool.setuptools.package-data]` names it. It is the PEP 561
  marker: without it a type checker in either app treats every shared name as `Any`, so the
  annotations exist and no tool is permitted to read them. The release gate asserts it.
- **`license = "MIT"` with `license-files`** is the PEP 639 form, which is why `[build-system]`
  requires `setuptools>=77`. Do not add a `License :: OSI Approved` classifier alongside it —
  setuptools rejects the pair.
- **`__version__` is a literal in source**, not an `importlib.metadata` lookup. Both apps ship as
  PyInstaller onefile builds with no `--copy-metadata`, and PyInstaller bundles modules rather
  than `.dist-info` directories, so a metadata lookup would raise `PackageNotFoundError` at import
  time inside the shipped executable. Nothing would catch it: every job in all three repos runs
  from a source tree against a pip-installed package, and the apps' release workflows build the
  executable without ever running it.
