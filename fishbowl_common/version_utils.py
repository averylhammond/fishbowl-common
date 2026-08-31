import re

# Matches the leading run of digits in one dotted version segment, so a segment
# carrying a pre-release or post-release suffix ("0-rc1", "0b1", "post1")
# contributes the number it starts with rather than failing to parse.
LEADING_DIGITS = re.compile(r"\d+")


###############################################################################
###                            parse_version()                              ###
###############################################################################
def parse_version(version: str) -> tuple[int, ...]:
    """
    Parses a version string into a tuple of integers for semantic comparison.

    Comparing the integer tuples (rather than the raw strings) keeps the ordering
    numeric, so "3.10.0" correctly sorts after "3.9.0".

    Parsing never raises: a segment with no leading digits ends the version, and
    an unrecognizable string yields an empty tuple. Callers turn a bad version
    into their own quiet outcome (a silent None, an empty notes string) rather
    than an exception surfacing as an unrelated failure.

    A pre-release therefore sorts equal to its final release: "2.2.0-rc1" and
    "2.2.0" both parse to (2, 2, 0). Ordering those correctly is PEP 440's job
    and would mean taking `packaging` as a runtime dependency, which this package
    deliberately does not.

    Args:
        version: A dotted version string, optionally prefixed with "v" (e.g. "v3.1.0" or
            "3.1.0").

    Returns:
        The version's numeric segments, e.g. (3, 1, 0).
    """

    segments = []

    for segment in version.lstrip("vV").split("."):
        match = LEADING_DIGITS.match(segment)

        # A segment that does not start with a digit ends the version: whatever
        # follows is a suffix rather than another numeric component
        if not match:
            break

        segments.append(int(match.group()))

    return tuple(segments)


###############################################################################
###                          compare_versions()                             ###
###############################################################################
def compare_versions(left: str, right: str) -> int:
    """
    Compares two version strings semantically.

    The parsed tuples are zero-padded to the same length before they are
    compared, so versions written with different numbers of segments compare as
    the same version: "1.2" and "1.2.0" are equal rather than the shorter one
    sorting first, which would report an update that does not exist.

    Args:
        left: The version to compare.
        right: The version to compare it against.

    Returns:
        -1 if left is older than right, 0 if they are the same version, and 1 if left is
        newer.
    """

    left_segments = parse_version(left)
    right_segments = parse_version(right)

    # Pad both to the same length so the comparison runs over matching segments
    length = max(len(left_segments), len(right_segments))
    left_padded = left_segments + (0,) * (length - len(left_segments))
    right_padded = right_segments + (0,) * (length - len(right_segments))

    if left_padded < right_padded:
        return -1

    if left_padded > right_padded:
        return 1

    return 0
