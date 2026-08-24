---
description: Checklist for adding a new class, module, or public name to fishbowl-common. Use when adding a new module, new window, new public export, or new shared helper to this package.
---

# Add a module

## 1. Decide which half it belongs in

- `fishbowl_common/` is **headless** and imports nothing but the standard library.
- `fishbowl_common/gui/` holds the tkinter windows, behind the `[gui]` extra.

If a headless module needs to talk to a window, **give it a `typing.Protocol`, not an import** —
that is how `UpdateCoordinator` takes an `UpdateDisplay` without dragging tkinter into the
headless half. `tests/headless_import_tests.py` fails the build if the split is ever broken.

If only one app wants it, it does not belong here at all; this package is for what both apps need.

## 2. Take app-specific values by constructor injection

No module-level default path, no environment variable, no import of a consumer's `constants`, no
application name or repo baked in anywhere. When a new value is needed, add a parameter — and
where a default is genuinely generic, make it generic by construction rather than by picking one
app's value.

## 3. Decide how it fails

- If the user must act on the failure, take
  `report_error: Callable[[str, str], None] = lambda *_: None`, store it, and invoke it as
  `(title, message)` from inside one `except` block per method, never re-raising. See
  `.claude/rules/settings-repository.md`.
- If the failure is cosmetic or a background check, **fail silently** — return `None`/`False`/`""`
  and let the caller decide whether the user hears about it. See `.claude/rules/update-classes.md`.

## 4. Add it to zero dependencies

Every import in both halves is stdlib. Taking a runtime dependency is a deliberate decision that
moves `README.md`, `pyproject.toml` and both apps' installs together — not a local edit.

## 5. Wire up the exports

Add the name to **both** the import block and `__all__` in the matching package root
(`fishbowl_common/__init__.py` or `fishbowl_common/gui/__init__.py`). Consumers import from those
names, not from the individual modules. If you added a **subpackage**, also add it to
`[tool.setuptools]` in `pyproject.toml`, or the release workflow's wheel smoke-install will ship a
half-empty wheel.

## 6. Write the tests

Create `tests/<ClassName>_tests.py` (or `tests/gui/<ClassName>_tests.py`). **Open the reference
implementation first** — `tests/UpdateCoordinator_tests.py` for a class with injected
collaborators, `tests/gui/UpdateWindow_tests.py` for a window — and mirror it. Reading either one
loads the full conventions from `.claude/rules/tests.md`. Coverage is at 100% on every measured
module; a new module landing untested should fail the check.

## 7. Update the documentation in the same change

Add the one-line entry to the module table in `CLAUDE.md`, and put any non-obvious rationale in
the matching `.claude/rules/` file. This is part of the definition of done, not an afterthought.

## 8. If it changed a public signature

It is step 1 of three. See `/move-the-pin`.
