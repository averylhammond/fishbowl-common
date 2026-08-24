---
description: Cuts a fishbowl-common release. Use when asked to release, cut a release, bump the version, tag a version, or publish a new version of this package.
disable-model-invocation: true
---

# Cut a release

The version lives in exactly one place, `version` in `pyproject.toml`, and is published by tag.
Pushing a `v*` tag is what runs `.github/workflows/release.yml`, and that workflow refuses to
publish a tag the repo does not already document.

## Steps

1. **Confirm the release contents.** `git log <last-tag>..HEAD --oneline` and check what is
   sitting under `## [Unreleased]` in `CHANGELOG.md`.
2. **Pick the version.** Semver against the last tag. A changed public signature is a minor bump
   at least, and means this release is step 1 of three — see `/move-the-pin`.
3. **Bump `version` in `pyproject.toml`.**
4. **Move `CHANGELOG.md`'s `## [Unreleased]` content under a `## [X.Y.Z] - YYYY-MM-DD` heading.**
   The changelog entry lands **with** the bump, not after it. Keep the existing heading format
   exactly: `release.yml` greps for `## [X.Y.Z]`, and reformatting the headings makes the check
   silently match nothing.
5. **Verify locally before tagging:** `pytest` passes, and the tag you are about to push equals
   the `version` you just wrote.
6. **Merge through a PR**, with a subject line carrying the `(vX.Y.Z)` marker.
7. **Push the tag** from the merged commit on `main`:
   `git checkout main && git pull && git tag vX.Y.Z && git push origin vX.Y.Z`.
8. **Watch the workflow.** `gh run watch` — it runs two `::error::` gates, `pytest`,
   `python -m build`, a fresh-venv wheel smoke-install of both halves, then
   `gh release create --generate-notes` with the sdist and wheel attached.

## The two gates that will fail you

- The tag must equal `pyproject.toml`'s `version`.
- `CHANGELOG.md` must carry a `## [X.Y.Z]` section for the tag.

Together they are what makes the pin trustworthy: the changelog is the answer to "what do I get
by moving the pin", and it cannot fall behind the version without failing the release. The
workflow's other load-bearing details are in `.claude/rules/ci-and-packaging.md`.

## History

Tags to date: `v1.3.0`, `v1.2.1`, `v1.2.0`, `v1.1.0`, `v1.0.1`, `v0.1.0`. The five predating the
release workflow (`v0.1.0` through `v1.2.1`) were pushed by hand and have no GitHub Release behind
them; they are backfilled in `CHANGELOG.md` and still work as pins, since a git ref is all a pin
needs.

## After the tag lands

The release is not delivered until the two consuming apps move their pins. Continue with
`/move-the-pin`.
