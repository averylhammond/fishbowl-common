import json
import urllib.error
from unittest.mock import patch, MagicMock

from fishbowl_common.UpdateChecker import UpdateChecker, REQUEST_TIMEOUT_SECONDS

# Repository used to construct the checker under test. Any "owner/name" value works;
# the checker derives its GitHub API URL from it.
_TEST_REPO = "owner/repo"


###############################################################################
###                     UpdateChecker -> Test Helpers                       ###
###############################################################################
def _release_response(tag_name: str, html_url: str = "https://example.com/release"):
    """
    Builds a mock object mimicking the context manager returned by
    urllib.request.urlopen, whose read() yields a GitHub releases API JSON body.

    Args:
        tag_name (str): The release tag to embed under "tag_name".
        html_url (str): The release page URL to embed under "html_url".

    Returns:
        unittest.mock.MagicMock: A mock suitable as urlopen's return value, usable
            in a `with` statement.
    """

    body = json.dumps({"tag_name": tag_name, "html_url": html_url}).encode()

    mock_response = MagicMock()
    mock_response.read.return_value = body

    # The object bound by `with urllib.request.urlopen(...) as response`
    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_response
    return mock_context


###############################################################################
###               Tests UpdateChecker -> check_for_update()                 ###
###############################################################################
@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_returns_result_when_newer_release_exists(mock_urlopen):
    """
    Verifies that a release newer than the running version yields a result flagged
    as an available update, with the version and release URL parsed from the
    response.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.return_value = _release_response(
        "v3.2.0", "https://example.com/v3.2.0"
    )

    result = UpdateChecker(
        current_version="3.1.2", repo=_TEST_REPO
    ).check_for_update()

    assert result.update_available is True
    assert result.latest_version == "3.2.0"
    assert result.release_url == "https://example.com/v3.2.0"


@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_no_update_when_versions_equal(mock_urlopen):
    """
    Verifies that a release matching the running version is not flagged as an
    available update.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.return_value = _release_response("v3.1.2")

    result = UpdateChecker(
        current_version="3.1.2", repo=_TEST_REPO
    ).check_for_update()

    assert result.update_available is False
    assert result.latest_version == "3.1.2"


@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_no_update_when_release_is_older(mock_urlopen):
    """
    Verifies that a release older than the running version is not flagged as an
    available update.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.return_value = _release_response("v3.1.0")

    result = UpdateChecker(
        current_version="3.1.2", repo=_TEST_REPO
    ).check_for_update()

    assert result.update_available is False


@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_normalizes_v_prefix_inconsistency(mock_urlopen):
    """
    Verifies that the comparison still works when the release tag carries a "v"
    prefix but the running version does not (the real-world tag format mismatch).

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.return_value = _release_response("v3.2.0")

    result = UpdateChecker(
        current_version="3.1.2", repo=_TEST_REPO
    ).check_for_update()

    assert result.update_available is True
    assert result.latest_version == "3.2.0"


@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_compares_versions_semantically_not_lexically(mock_urlopen):
    """
    Verifies that versions are compared numerically, so "3.10.0" is treated as newer
    than "3.9.0" (a raw string comparison would get this backwards).

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.return_value = _release_response("v3.10.0")

    result = UpdateChecker(
        current_version="3.9.0", repo=_TEST_REPO
    ).check_for_update()

    assert result.update_available is True


@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_requests_latest_release_url_with_timeout(mock_urlopen):
    """
    Verifies that the check queries the repo's GitHub latest-release endpoint,
    derived from the injected "owner/name", and caps the request with the configured
    timeout.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.return_value = _release_response("v3.1.2")

    UpdateChecker(current_version="3.1.2", repo=_TEST_REPO).check_for_update()

    mock_urlopen.assert_called_once_with(
        f"https://api.github.com/repos/{_TEST_REPO}/releases/latest",
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_returns_none_on_network_error(mock_urlopen):
    """
    Verifies that a network failure is swallowed and reported as None rather than
    raising, so a background check never interrupts the user.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.side_effect = urllib.error.URLError("no network")

    result = UpdateChecker(
        current_version="3.1.2", repo=_TEST_REPO
    ).check_for_update()

    assert result is None


@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_returns_none_on_malformed_response(mock_urlopen):
    """
    Verifies that a response body that is not valid JSON is swallowed and reported
    as None.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_response = MagicMock()
    mock_response.read.return_value = b"not json"
    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_context

    result = UpdateChecker(
        current_version="3.1.2", repo=_TEST_REPO
    ).check_for_update()

    assert result is None
