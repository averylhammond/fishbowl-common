from pathlib import Path
from unittest.mock import MagicMock

from fishbowl_common.PatchNotes import PatchNotes

# A notes file shaped like the one an application ships: a short preamble that
# belongs to no version, then one section per release, newest first.
_NOTES = "\n".join(
    [
        "# Patch Notes",
        "",
        "What changed in each release.",
        "",
        "## 2.4.0",
        "",
        "- Added the fourth thing",
        "",
        "## 2.3.0",
        "",
        "- Added the third thing",
        "",
        "## 2.2.0",
        "",
        "- Added the second thing",
        "",
    ]
)


###############################################################################
###                       PatchNotes -> Test Helpers                        ###
###############################################################################
def _reader(contents: str = _NOTES):
    """
    Builds a PatchNotes reader over a mocked notes file, so no test touches the
    real filesystem.

    Args:
        contents (str): The notes file contents the reader should see

    Returns:
        PatchNotes: A reader whose injected path returns the given contents
    """

    notes_path = MagicMock(spec=Path)
    notes_path.read_text.return_value = contents

    return PatchNotes(notes_path)


def _failing_reader(error: Exception):
    """
    Builds a PatchNotes reader whose notes file cannot be read.

    Args:
        error (Exception): The exception the read should raise

    Returns:
        PatchNotes: A reader whose injected path raises when it is read
    """

    notes_path = MagicMock(spec=Path)
    notes_path.read_text.side_effect = error

    return PatchNotes(notes_path)


###############################################################################
###                    Tests PatchNotes -> notes_since()                    ###
###############################################################################
def test_notes_since_returns_the_section_for_a_single_new_version():
    """
    Verifies that a user who updated by one release is shown that release's
    section, heading included, and nothing else.
    """

    notes = _reader().notes_since("2.3.0", "2.2.0")

    assert notes == "## 2.3.0\n\n- Added the third thing"


def test_notes_since_returns_every_skipped_version_newest_first():
    """
    Verifies that a user who skipped a release and updated straight past it is
    shown both sections, newest first. This is the reason the reader returns a
    range rather than looking up one version's notes.
    """

    notes = _reader().notes_since("2.4.0", "2.2.0")

    assert notes == (
        "## 2.4.0\n\n- Added the fourth thing\n\n## 2.3.0\n\n- Added the third thing"
    )


def test_notes_since_orders_sections_by_version_not_file_order():
    """
    Verifies that the sections come back newest first even when the file lists
    them oldest first, so a notes file written in either order reads correctly.
    """

    oldest_first = "\n".join(
        ["## 2.3.0", "", "- Added the third thing", "", "## 2.4.0", "", "- Added the fourth thing"]
    )

    notes = _reader(oldest_first).notes_since("2.4.0", "2.2.0")

    assert notes.startswith("## 2.4.0")


def test_notes_since_ignores_versions_newer_than_the_running_one():
    """
    Verifies that a section for a version above the running one is not shown, so
    an application never announces changes the user does not actually have.
    """

    notes = _reader().notes_since("2.3.0", "2.2.0")

    assert "2.4.0" not in notes


def test_notes_since_returns_nothing_when_last_seen_matches_current():
    """
    Verifies that an ordinary relaunch, where the user has already seen the
    running version, produces nothing to show.
    """

    assert _reader().notes_since("2.4.0", "2.4.0") == ""


def test_notes_since_returns_nothing_when_last_seen_is_newer():
    """
    Verifies that a downgrade or a sideways install produces nothing to show,
    rather than notes for versions the user has already seen.
    """

    assert _reader().notes_since("2.3.0", "2.4.0") == ""


def test_notes_since_without_a_last_seen_version_has_no_lower_bound():
    """
    Verifies that passing None for the last seen version returns every section
    up to the running one. Deciding that a fresh install should be shown nothing
    belongs to the caller, which is the only side that can tell a fresh install
    from an upgrade.
    """

    notes = _reader().notes_since("2.3.0", None)

    assert "2.3.0" in notes
    assert "2.2.0" in notes
    assert "2.4.0" not in notes


def test_notes_since_tolerates_a_v_prefixed_heading():
    """
    Verifies that a section headed with a leading "v" is matched, since release
    tags carry one inconsistently.
    """

    notes = _reader("## v2.3.0\n\n- Added the third thing").notes_since("2.3.0", "2.2.0")

    assert notes == "## v2.3.0\n\n- Added the third thing"


def test_notes_since_tolerates_a_heading_with_a_trailing_date():
    """
    Verifies that a section headed with a release date after the version is
    matched, since a changelog usually carries one.
    """

    notes = _reader("## 2.3.0 - 2026-08-21\n\n- Added it").notes_since("2.3.0", "2.2.0")

    assert notes == "## 2.3.0 - 2026-08-21\n\n- Added it"


def test_notes_since_tolerates_a_bracketed_heading():
    """
    Verifies that a Keep a Changelog heading, which wraps the version in square
    brackets, is matched, so the same reader works against a changelog written in
    that format.
    """

    notes = _reader("## [2.3.0] - 2026-08-21\n\n- Added it").notes_since("2.3.0", "2.2.0")

    assert notes == "## [2.3.0] - 2026-08-21\n\n- Added it"


def test_notes_since_ignores_a_non_version_heading():
    """
    Verifies that a heading naming no version (an "Unreleased" section) is not
    treated as a version's notes, so unreleased content is never announced.
    """

    notes = _reader("## Unreleased\n\n- Not out yet").notes_since("2.3.0", "2.2.0")

    assert notes == ""


def test_notes_since_returns_nothing_for_a_file_with_no_headings():
    """
    Verifies that a notes file holding no version headings yields nothing to
    show rather than the whole file's text.
    """

    assert _reader("Just some prose with no headings.").notes_since("2.3.0", None) == ""


def test_notes_since_returns_nothing_when_the_file_is_missing():
    """
    Verifies that a missing or unreadable notes file yields an empty string. The
    notes are a cosmetic feature and must never be able to stop the application
    from starting.
    """

    assert _failing_reader(OSError("missing")).notes_since("2.3.0", "2.2.0") == ""


def test_notes_since_returns_nothing_when_the_file_cannot_be_decoded():
    """
    Verifies that a notes file that is not valid UTF-8 yields an empty string
    rather than raising out of the reader.
    """

    error = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    assert _failing_reader(error).notes_since("2.3.0", "2.2.0") == ""
