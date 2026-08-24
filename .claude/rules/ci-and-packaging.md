---
paths:
  - ".github/workflows/**"
  - "pyproject.toml"
---

# CI and packaging

**Do not remove `[tool.pytest.ini_options]`.** It sets `python_files = ["*_tests.py"]` and
`testpaths = ["tests"]`. This project names its test files with the `_tests.py` suffix, which
pytest's default `test_*.py` pattern does not match, so without that block a bare `pytest`
collects nothing and CI passes vacuously. (It is also why the two apps, which have no such block,
invoke `pytest tests/*`.)

## The three workflows

Two run on `pull_request` to `main` and `workflow_dispatch`; the third runs only on a pushed `v*`
tag. All three are `ubuntu-latest` with `actions/setup-python@v5` at `3.11.9` and
`pip install -e ".[dev,gui]"`.

`code-coverage.yml` sets `fail_ci_if_error: false` on `codecov/codecov-action@v5` deliberately —
the `--cov-fail-under` gate is what enforces coverage, so a Codecov outage must not mask it by
failing the job for an unrelated reason. It needs `CODECOV_TOKEN`.

## `release.yml` — four load-bearing things

- **The tag must equal `pyproject.toml`'s `version`**, read with `tomllib` (stdlib on 3.11, so
  the gate needs nothing installed). This is the apps' own check with the version source swapped,
  since there is no `constants.py` here.
- **`CHANGELOG.md` must carry a `## [X.Y.Z]` section for the tag**, which has no analog in the
  apps. That `grep` and the changelog's heading format are one contract: reformat the headings
  and the check silently matches nothing.
- **The built wheel is installed into a fresh venv and imported before publishing**, both halves
  of it. `[tool.setuptools]` lists the packaged subpackages explicitly, so a subpackage added to
  the tree but not to that list would otherwise ship a half-empty wheel. The step `cd`s out of the
  repo first — from the root, the working directory's own `fishbowl_common/` shadows the installed
  one and the import proves nothing.
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

Two divergences from the apps' equivalent workflows are **gaps, not decisions**, both tracked in
#11: the gate is **80 here against 90 in both apps**, and there is **no `push: branches: [main]`
trigger**, so Codecov records no main-branch baseline, the badge never updates and PR coverage
comments have nothing to compare against. Do not read either as an intentional mirror of the
apps' files, and do not fix one without the other.

One further gap is tracked rather than fixed: the packaging metadata has no `py.typed`, `LICENSE`
or `__version__` — the annotations are written throughout and then discarded at the package
boundary (#9).
