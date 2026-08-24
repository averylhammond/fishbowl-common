from fishbowl_common.version_utils import compare_versions, parse_version


###############################################################################
###                     Tests version_utils -> parse_version()              ###
###############################################################################
def test_parse_version_splits_a_dotted_version_into_integers():
    """
    Verifies that an ordinary dotted version is parsed into one integer per
    segment, which is what makes the comparison numeric rather than lexical.
    """

    assert parse_version("3.1.0") == (3, 1, 0)


def test_parse_version_strips_a_leading_v():
    """
    Verifies that a leading "v" is ignored, since release tags carry one
    inconsistently and a tag must compare equal to the bare version it names.
    """

    assert parse_version("v3.1.0") == parse_version("3.1.0")


def test_parse_version_accepts_a_pre_release_suffix():
    """
    Verifies that a pre-release tag parses to its numeric version instead of
    raising. A raised exception here was reported to the user as a failed update
    check, making a perfectly successful check look like a network outage.
    """

    assert parse_version("v2.2.0-rc1") == (2, 2, 0)


def test_parse_version_accepts_a_post_release_suffix():
    """
    Verifies that a suffix attached without punctuation (a post-release or beta
    segment) parses to the number it starts with rather than raising.
    """

    assert parse_version("1.0.0.post1") == (1, 0, 0)
    assert parse_version("2.2.0b1") == (2, 2, 0)


def test_parse_version_returns_empty_tuple_for_an_unparseable_version():
    """
    Verifies that a version with no leading digits at all yields an empty tuple
    rather than raising, so a caller handed a garbage version reports its own
    quiet outcome instead of an exception.
    """

    assert parse_version("") == ()
    assert parse_version("not-a-version") == ()


###############################################################################
###                   Tests version_utils -> compare_versions()             ###
###############################################################################
def test_compare_versions_reports_a_newer_version():
    """
    Verifies that a strictly newer version compares greater, which is the check
    an update is offered on.
    """

    assert compare_versions("3.2.0", "3.1.0") == 1


def test_compare_versions_reports_an_older_version():
    """
    Verifies that an older version compares less, so a release behind the
    running build is never offered as an update.
    """

    assert compare_versions("3.0.0", "3.1.0") == -1


def test_compare_versions_reports_equal_versions():
    """
    Verifies that the same version on both sides compares equal.
    """

    assert compare_versions("3.1.0", "3.1.0") == 0


def test_compare_versions_pads_unequal_segment_counts():
    """
    Verifies that versions written with different numbers of segments compare as
    the same version. Without padding "1.2" sorted below "1.2.0", so a user
    already on 1.2.0 was told a 1.2 release was an update.
    """

    assert compare_versions("1.2", "1.2.0") == 0
    assert compare_versions("1.2.0", "1.2") == 0
    assert compare_versions("1.2.1", "1.2") == 1


def test_compare_versions_compares_numerically_not_lexically():
    """
    Verifies that a double-digit segment sorts above a single-digit one, which a
    string comparison of the raw versions would get backwards.
    """

    assert compare_versions("3.10.0", "3.9.0") == 1
