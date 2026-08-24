import json
import urllib.error
from unittest.mock import patch, MagicMock

from fishbowl_common.UpdateChecker import (
    UpdateChecker,
    CHECK_ERROR_HTTP,
    CHECK_ERROR_NETWORK,
    CHECK_ERROR_RATE_LIMITED,
    CHECK_ERROR_RESPONSE,
    DEFAULT_CHECKSUMS_NAME,
    REQUEST_TIMEOUT_SECONDS,
)

# Repository used to construct the checker under test. Any "owner/name" value works;
# the checker derives its GitHub API URL from it.
_TEST_REPO = "owner/repo"

# The endpoint the checker derives from _TEST_REPO, named once so a test asserting
# the request does not rebuild it.
_LATEST_RELEASE_URL = f"https://api.github.com/repos/{_TEST_REPO}/releases/latest"


###############################################################################
###                     UpdateChecker -> Test Helpers                       ###
###############################################################################
def _release_response(
    tag_name: str,
    html_url: str = "https://example.com/release",
    assets: list | None = None,
):
    """
    Builds a mock object mimicking the context manager returned by
    urllib.request.urlopen, whose read() yields a GitHub releases API JSON body.

    Args:
        tag_name (str): The release tag to embed under "tag_name".
        html_url (str): The release page URL to embed under "html_url".
        assets (list | None): The published files to embed under "assets", each
            shaped like the API's asset objects; None omits the key entirely, as an
            unexpected response shape would.

    Returns:
        unittest.mock.MagicMock: A mock suitable as urlopen's return value, usable
            in a `with` statement.
    """

    release = {"tag_name": tag_name, "html_url": html_url}
    if assets is not None:
        release["assets"] = assets

    body = json.dumps(release).encode()

    mock_response = MagicMock()
    mock_response.read.return_value = body

    # The object bound by `with urllib.request.urlopen(...) as response`
    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_response
    return mock_context


def _http_error(code: int, headers: dict | None = None):
    """
    Builds the HTTPError urlopen raises when GitHub answers with a status instead of
    a release.

    Args:
        code (int): The HTTP status GitHub answered with.
        headers (dict | None): The response headers, e.g. the rate-limit headers a
            refusal carries; None stands for a response carrying none at all.

    Returns:
        urllib.error.HTTPError: The error to raise from the mocked urlopen.
    """

    return urllib.error.HTTPError(_LATEST_RELEASE_URL, code, "refused", headers, None)


def _asset(name: str, size: int = 1024):
    """
    Builds one entry of a release's "assets" array, shaped like the GitHub API's
    asset objects.

    Args:
        name (str): The asset's published filename.
        size (int): The asset's size in bytes.

    Returns:
        dict: The asset object to embed in a release response.
    """

    return {
        "name": name,
        "browser_download_url": f"https://example.com/{name}",
        "size": size,
    }


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
def test_check_for_update_handles_a_pre_release_tag(mock_urlopen):
    """
    Verifies that a release tagged as a pre-release yields an ordinary result
    rather than None. A pre-release tag used to raise while the version was being
    parsed, which the broad handler turned into None - reported to the user as a
    failed check, so a perfectly successful one looked like a network outage.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.return_value = _release_response("v2.2.0-rc1")

    result = UpdateChecker(
        current_version="2.1.0", repo=_TEST_REPO
    ).check_for_update()

    assert result is not None
    assert result.update_available is True


@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_no_update_when_the_release_omits_a_segment(mock_urlopen):
    """
    Verifies that a release written with fewer segments than the running version
    is not offered as an update: "1.2" and "1.2.0" are the same version, but
    comparing them segment by segment used to sort the shorter one first.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.return_value = _release_response("v1.2")

    result = UpdateChecker(
        current_version="1.2.0", repo=_TEST_REPO
    ).check_for_update()

    assert result.update_available is False


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

    mock_urlopen.assert_called_once()
    assert mock_urlopen.call_args.args[0].full_url == _LATEST_RELEASE_URL
    assert mock_urlopen.call_args.kwargs == {"timeout": REQUEST_TIMEOUT_SECONDS}


@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_identifies_itself_to_the_github_api(mock_urlopen):
    """
    Verifies that the request carries the headers GitHub's API expects: a User-Agent
    (documented as required, and rejectable when absent) and the Accept and version
    headers pinning the response to the schema this parses.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.return_value = _release_response("v3.1.2")

    UpdateChecker(current_version="3.1.2", repo=_TEST_REPO).check_for_update()

    # Request title-cases the header names it is handed, so compare on lowered keys
    sent = {
        name.lower(): value
        for name, value in mock_urlopen.call_args.args[0].header_items()
    }

    assert sent["user-agent"] == "fishbowl-common"
    assert sent["accept"] == "application/vnd.github+json"
    assert sent["x-github-api-version"] == "2022-11-28"


@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_returns_none_on_network_error(mock_urlopen):
    """
    Verifies that a network failure is swallowed and reported as None rather than
    raising, so a background check never interrupts the user.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.side_effect = urllib.error.URLError("no network")

    checker = UpdateChecker(current_version="3.1.2", repo=_TEST_REPO)

    assert checker.check_for_update() is None
    assert checker.last_error == CHECK_ERROR_NETWORK


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

    checker = UpdateChecker(current_version="3.1.2", repo=_TEST_REPO)

    assert checker.check_for_update() is None
    assert checker.last_error == CHECK_ERROR_RESPONSE


###############################################################################
###               Tests UpdateChecker -> last_error reporting               ###
###############################################################################
@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_reports_an_exhausted_rate_limit(mock_urlopen):
    """
    Verifies that GitHub refusing the check because the hourly budget is spent is
    reported as a rate limit rather than as a network failure. The unauthenticated
    API allows 60 requests/hour/IP and a whole office shares one, so this is the
    failure a caller most needs to word differently.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.side_effect = _http_error(403, {"X-RateLimit-Remaining": "0"})

    checker = UpdateChecker(current_version="3.1.2", repo=_TEST_REPO)

    assert checker.check_for_update() is None
    assert checker.last_error == CHECK_ERROR_RATE_LIMITED


@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_reports_a_rate_limit_carrying_only_retry_after(mock_urlopen):
    """
    Verifies that a refusal telling the caller when to come back is read as a rate
    limit even though it reports requests still remaining, which is how GitHub
    answers a secondary limit with a 403.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.side_effect = _http_error(
        403, {"X-RateLimit-Remaining": "42", "Retry-After": "60"}
    )

    checker = UpdateChecker(current_version="3.1.2", repo=_TEST_REPO)

    assert checker.check_for_update() is None
    assert checker.last_error == CHECK_ERROR_RATE_LIMITED


@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_reports_too_many_requests_as_a_rate_limit(mock_urlopen):
    """
    Verifies that a 429 is read as a rate limit on the status alone, since it is
    never anything else and need not carry the rate-limit headers.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.side_effect = _http_error(429)

    checker = UpdateChecker(current_version="3.1.2", repo=_TEST_REPO)

    assert checker.check_for_update() is None
    assert checker.last_error == CHECK_ERROR_RATE_LIMITED


@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_reports_an_ordinary_refusal_as_an_http_failure(mock_urlopen):
    """
    Verifies that a 403 with requests still remaining and no retry advice is not
    mistaken for a rate limit - GitHub answers an ordinary refusal with the same
    status, and telling the user to wait it out would be wrong.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.side_effect = _http_error(403, {"X-RateLimit-Remaining": "57"})

    checker = UpdateChecker(current_version="3.1.2", repo=_TEST_REPO)

    assert checker.check_for_update() is None
    assert checker.last_error == CHECK_ERROR_HTTP


@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_reports_a_missing_release_as_an_http_failure(mock_urlopen):
    """
    Verifies that a repository publishing no releases (a 404) is reported as an HTTP
    failure, so it is neither blamed on a rate limit nor on the network.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.side_effect = _http_error(404)

    checker = UpdateChecker(current_version="3.1.2", repo=_TEST_REPO)

    assert checker.check_for_update() is None
    assert checker.last_error == CHECK_ERROR_HTTP


@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_clears_the_error_once_a_check_succeeds(mock_urlopen):
    """
    Verifies that a successful check leaves no error behind, so a caller reusing a
    checker cannot report a failure that has since resolved itself.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    checker = UpdateChecker(current_version="3.1.2", repo=_TEST_REPO)

    mock_urlopen.side_effect = _http_error(429)
    checker.check_for_update()

    mock_urlopen.side_effect = None
    mock_urlopen.return_value = _release_response("v3.2.0")

    assert checker.check_for_update() is not None
    assert checker.last_error is None


###############################################################################
###              Tests UpdateChecker -> release asset lookup                ###
###############################################################################
@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_surfaces_the_installer_and_checksums_assets(mock_urlopen):
    """
    Verifies that the release's installer (matched against the injected pattern) and
    its checksums file are both surfaced from the same request, so an application
    that installs the update itself needs no second call.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.return_value = _release_response(
        "v3.2.0",
        assets=[
            _asset("App.zip"),
            _asset("App_Setup.exe", size=4096),
            _asset(DEFAULT_CHECKSUMS_NAME, size=128),
        ],
    )

    result = UpdateChecker(
        current_version="3.1.2", repo=_TEST_REPO, asset_pattern="App_Setup.exe"
    ).check_for_update()

    assert result.installer_asset.name == "App_Setup.exe"
    assert result.installer_asset.download_url == "https://example.com/App_Setup.exe"
    assert result.installer_asset.size == 4096
    assert result.checksums_asset.name == DEFAULT_CHECKSUMS_NAME


@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_matches_the_installer_by_glob_pattern(mock_urlopen):
    """
    Verifies that the asset pattern is matched with fnmatch rather than by equality,
    so a consumer can name its installer by shape when the filename carries the
    version or another varying part.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.return_value = _release_response(
        "v3.2.0", assets=[_asset("App-3.2.0_Setup.exe")]
    )

    result = UpdateChecker(
        current_version="3.1.2", repo=_TEST_REPO, asset_pattern="*_Setup.exe"
    ).check_for_update()

    assert result.installer_asset.name == "App-3.2.0_Setup.exe"


@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_reports_no_installer_when_none_matches(mock_urlopen):
    """
    Verifies that a release publishing nothing that matches the pattern still yields
    a result, with no installer asset on it. An older release predating the
    installer is an ordinary outcome, not a failed check.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.return_value = _release_response(
        "v3.2.0", assets=[_asset("App.zip"), _asset(DEFAULT_CHECKSUMS_NAME)]
    )

    result = UpdateChecker(
        current_version="3.1.2", repo=_TEST_REPO, asset_pattern="App_Setup.exe"
    ).check_for_update()

    assert result.update_available is True
    assert result.installer_asset is None
    assert result.checksums_asset is not None


@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_reports_no_installer_without_an_asset_pattern(mock_urlopen):
    """
    Verifies that a consumer injecting no asset pattern gets no installer asset,
    even when the release publishes one - the pattern is how an application names
    its own installer, and guessing one would break the application-agnostic rule
    this package is built on.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.return_value = _release_response(
        "v3.2.0", assets=[_asset("App_Setup.exe")]
    )

    result = UpdateChecker(current_version="3.1.2", repo=_TEST_REPO).check_for_update()

    assert result.installer_asset is None


@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_reports_no_assets_when_the_release_lists_none(mock_urlopen):
    """
    Verifies that a response carrying no "assets" key at all is handled like a
    release with no assets rather than raising, so an unexpected response shape
    still leaves the manual download flow working.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.return_value = _release_response("v3.2.0")

    result = UpdateChecker(
        current_version="3.1.2", repo=_TEST_REPO, asset_pattern="App_Setup.exe"
    ).check_for_update()

    assert result.installer_asset is None
    assert result.checksums_asset is None


@patch("fishbowl_common.UpdateChecker.urllib.request.urlopen")
def test_check_for_update_finds_the_checksums_asset_by_injected_name(mock_urlopen):
    """
    Verifies that the checksums asset is looked up by the injected name, so a
    consumer whose pipeline publishes it under a different filename is not stuck
    with the default.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
    """

    mock_urlopen.return_value = _release_response(
        "v3.2.0", assets=[_asset("checksums.txt")]
    )

    result = UpdateChecker(
        current_version="3.1.2", repo=_TEST_REPO, checksums_name="checksums.txt"
    ).check_for_update()

    assert result.checksums_asset.name == "checksums.txt"
