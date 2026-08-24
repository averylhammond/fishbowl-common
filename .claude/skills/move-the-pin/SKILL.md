---
description: Plans the three-repo rollout when a fishbowl-common change alters a public signature. Use when changing a constructor, method signature, or public name that FishbowlInvoiceTool or FishbowlInventoryTool calls, or when asked how a change reaches the apps.
---

# Move the pin

Consumers take this package as a **pinned git tag**, never as a path or a submodule. Both apps
carry the byte-identical pin at `requirements/release.txt:1`:

```
fishbowl-common[gui] @ git+https://github.com/averylhammond/fishbowl-common.git@v1.2.1
```

**A change here reaches an app only when that app moves its pin.** That cuts both ways: work can
land on `main` here without breaking anything downstream, and a fix is not actually delivered
until two other repos are edited.

## A public-signature change is three PRs, in order

1. **Here** — make the change, then cut a release: bump `__version__` in
   `fishbowl_common/_version.py`, add the matching `## [X.Y.Z]` section to `CHANGELOG.md`,
   merge, push the `vX.Y.Z` tag. Use `/cut-a-release` for the full procedure.
2. **`FishbowlInvoiceTool`** — move the pin to the new tag, adapt the call sites, merge.
3. **`FishbowlInventoryTool`** — the same.

Plan for that shape of work up front rather than discovering it at step 2.

## What counts as a public-signature change

Anything a consumer calls or implements: a constructor parameter, a method signature, a renamed
public export, or a Protocol method. `UpdateDisplay` is the sharp case — both apps *implement* it
structurally, so adding a method to the Protocol breaks both without any import to warn you.

## The precedent

`v1.2.0` changed `show_update_available()` to take a second `start_install` argument — a method
both apps implement, so both had to move together. That is the shape to expect.

## Before you start

Check whether the change can stay backward-compatible instead: a new parameter with a generic
default keeps both apps working on the old pin, and they can adopt it whenever they next move.
The `checksums_name` parameter on `UpdateChecker` and `description` on `ArgumentProvider` are
both examples of a default made generic by construction rather than by picking one app's value.
