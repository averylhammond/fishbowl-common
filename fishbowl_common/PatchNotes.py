import functools
import re
from pathlib import Path

from fishbowl_common.version_utils import compare_versions

# Matches one changelog section heading and captures the version it announces.
# Three tolerances are deliberate: a leading "v" (release tags use one
# inconsistently), a "[...]" wrapper (the Keep a Changelog format), and any
# trailing remainder after the version (usually the release date), so a heading
# reads "## 2.3.0", "## v2.3.0" or "## [2.3.0] - 2026-08-21" equally well.
SECTION_HEADING = re.compile(r"^##\s+\[?v?(\d+(?:\.\d+)*)\]?\s*(?:[-–—].*)?$")

# Separator placed between the sections of consecutive versions when several are
# shown at once, so each release's notes read as its own block.
SECTION_SEPARATOR = "\n\n"


# PatchNotes reads the changelog file an application ships alongside its
# executable and picks out the sections describing the versions a user has not
# seen yet, so the application can show them what an update changed. It reads a
# local file rather than a release's notes on GitHub, so the first launch after
# an update needs no network. The file it is pointed at is injected, so this
# class carries no knowledge of which application it belongs to.
class PatchNotes:

    ###########################################################################
    ###                       PatchNotes -> __init__()                      ###
    ###########################################################################
    def __init__(self, notes_path: Path):
        """
        Initializes the PatchNotes reader with the file it reads from.

        The file is read on each call rather than here, so constructing this
        object cannot fail and a caller can hold one for the life of the
        application.

        Args:
            notes_path (Path): The changelog file shipped with the application,
                holding one "## X.Y.Z" section per released version.
        """

        self.notes_path = notes_path

    ###########################################################################
    ###                     PatchNotes -> notes_since()                     ###
    ###########################################################################
    def notes_since(self, current_version: str, last_seen_version: str | None) -> str:
        """
        Collects the notes for every version the user has not seen yet.

        A user who skips a release and updates straight past it should still be
        told what that release changed, so this returns every section strictly
        newer than last_seen_version and no newer than current_version, newest
        first, rather than one version's section.

        It fails silently: a missing, unreadable or unparseable file yields an
        empty string, exactly as if the release published no notes. Showing the
        user what changed is a cosmetic feature and must never be able to stop
        the application from starting.

        Args:
            current_version (str): The running application's version. Sections
                newer than this are ignored, so notes for a version the user is
                not actually running are never announced.
            last_seen_version (str | None): The version the user last launched,
                or None for no lower bound at all (every section up to and
                including current_version). Deciding that a user with no stored
                version should be shown nothing belongs to the caller, which is
                the only side that can tell a fresh install from an upgrade.

        Returns:
            str: The matching sections, newest first, separated by a blank line,
                or an empty string if there are none.
        """

        wanted = [
            (version, body)
            for version, body in self._read_sections()
            if compare_versions(version, current_version) <= 0
            and (
                last_seen_version is None
                or compare_versions(version, last_seen_version) > 0
            )
        ]

        # Order by version rather than trusting the file's own ordering. The
        # comparison is used as the sort key (rather than the parsed tuples) so
        # versions written with different segment counts still sort correctly.
        wanted.sort(
            key=functools.cmp_to_key(
                lambda left, right: compare_versions(left[0], right[0])
            ),
            reverse=True,
        )

        return SECTION_SEPARATOR.join(body for _version, body in wanted)

    ###########################################################################
    ###                    PatchNotes -> _read_sections()                   ###
    ###########################################################################
    def _read_sections(self) -> list[tuple[str, str]]:
        """
        Splits the notes file into one section per version.

        A section runs from its heading to the line before the next heading, and
        the heading line is kept as part of the section body so a result holding
        several versions still says which notes belong to which release.

        Returns:
            list[tuple[str, str]]: The version each section announces paired with
                the section's text, in the order they appear in the file. Empty
                if the file could not be read or holds no version headings.
        """

        try:
            contents = self.notes_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            # A missing or unreadable notes file is reported as having no notes,
            # leaving the caller with nothing to show rather than an error
            return []

        sections: list[tuple[str, list[str]]] = []

        for line in contents.splitlines():
            match = SECTION_HEADING.match(line.rstrip())

            if match:
                sections.append((match.group(1), [line]))
            elif sections:
                # Anything before the first heading is the file's preamble and
                # belongs to no version, so it is dropped
                sections[-1][1].append(line)

        # Trim each section's trailing blank lines, which are only the spacing
        # that separated it from the next heading in the file
        return [
            (version, "\n".join(lines).rstrip())
            for version, lines in sections
        ]
