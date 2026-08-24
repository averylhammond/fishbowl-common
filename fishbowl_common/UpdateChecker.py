import fnmatch
import json
import urllib.error
import urllib.request

from fishbowl_common.version_utils import compare_versions

# Cap how long the request may block so a slow or unreachable network can never
# stall a caller (e.g. an update check run on application startup).
REQUEST_TIMEOUT_SECONDS = 5

# Name of the release asset listing the SHA-256 digest of every other asset. The
# release pipeline publishes it so a downloaded installer can be verified before it
# is executed; it is named the same in every consuming repository, so it is a
# default rather than a required argument.
DEFAULT_CHECKSUMS_NAME = "SHA256SUMS.txt"

# Sent with every request to the GitHub API. GitHub documents the User-Agent as
# required and can reject a request carrying none; the other two pin the response to
# the schema this module parses, so a future default API version cannot silently
# reshape it. The User-Agent names the package rather than a consuming application,
# since both of them share this client.
# How this package identifies itself over HTTP. Named separately because
# UpdateDownloader sends it too, on requests that want none of the API headers
# below, and the two must not drift apart.
USER_AGENT = "fishbowl-common"

REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# What UpdateChecker.last_error carries after a failed check. The check still fails
# silently by returning None, and reading this is optional - but without it a rate
# limit (the unauthenticated API allows 60 requests/hour/IP, and a whole office
# shares one) is indistinguishable from an unplugged network cable, and the caller
# tells the user to go looking for a problem they do not have.
CHECK_ERROR_RATE_LIMITED = "rate_limited"
CHECK_ERROR_HTTP = "http"
CHECK_ERROR_NETWORK = "network"
CHECK_ERROR_RESPONSE = "response"

# The two statuses a rate-limited request comes back as: 403 for the exhausted
# hourly budget, 429 for a secondary limit.
FORBIDDEN_STATUS = 403
TOO_MANY_REQUESTS_STATUS = 429


# ReleaseAsset is a plain data holder describing one file published alongside a
# GitHub release, carrying what a downloader needs to fetch and size-check it.
class ReleaseAsset:

    ###########################################################################
    ###                      ReleaseAsset -> __init__()                     ###
    ###########################################################################
    def __init__(self, name: str, download_url: str, size: int | None):
        """
        Initializes the ReleaseAsset with the asset's identity and location.

        Args:
            name (str): The asset's filename as published on the release, e.g.
                "FishbowlInvoiceTool_Setup.exe".
            download_url (str): The asset's direct download URL.
            size (int | None): The asset's size in bytes as reported by GitHub, or
                None if the response did not carry one.
        """

        self.name = name
        self.download_url = download_url
        self.size = size


# UpdateCheckResult is a plain data holder describing the outcome of comparing the
# latest published release against the running application version.
class UpdateCheckResult:

    ###########################################################################
    ###                  UpdateCheckResult -> __init__()                    ###
    ###########################################################################
    def __init__(
        self,
        update_available: bool,
        latest_version: str,
        release_url: str,
        installer_asset: ReleaseAsset | None = None,
        checksums_asset: ReleaseAsset | None = None,
    ):
        """
        Initializes the UpdateCheckResult with the comparison outcome and the
        details needed to point the user at the new release.

        Args:
            update_available (bool): True if the latest published release is
                strictly newer than the running version.
            latest_version (str): The latest release's version, normalized with any
                leading "v" stripped (e.g. "3.1.0").
            release_url (str): The URL of the latest release's page on GitHub.
            installer_asset (ReleaseAsset | None): The release's installer, matched
                against the caller's asset pattern, or None when the release
                publishes no matching asset (or no pattern was injected).
            checksums_asset (ReleaseAsset | None): The release's checksums file,
                against which the installer is verified before it is executed, or
                None when the release publishes none.
        """

        self.update_available = update_available
        self.latest_version = latest_version
        self.release_url = release_url
        self.installer_asset = installer_asset
        self.checksums_asset = checksums_asset


# UpdateChecker queries the GitHub releases API for the latest published release
# and compares its version against the running application version, so the app can
# tell the user when a newer build is available. It also surfaces the release's
# installer and checksums assets, so an application that installs the update itself
# has everything it needs from the one request.
class UpdateChecker:

    ###########################################################################
    ###                    UpdateChecker -> __init__()                      ###
    ###########################################################################
    def __init__(
        self,
        current_version: str,
        repo: str,
        asset_pattern: str | None = None,
        checksums_name: str = DEFAULT_CHECKSUMS_NAME,
    ):
        """
        Initializes the UpdateChecker with the version to compare against and the
        repository to check for releases.

        Args:
            current_version (str): The running application's version, injected by the
                caller (typically from its own VERSION constant).
            repo (str): The GitHub repository in "owner/name" form whose latest
                release is compared against current_version.
            asset_pattern (str | None): An fnmatch pattern naming the release's
                installer, e.g. "FishbowlInvoiceTool_Setup.exe" or "*_Setup.exe".
                Injected because each application names its installer differently;
                when omitted, no installer asset is surfaced.
            checksums_name (str): Name of the release asset listing each asset's
                SHA-256 digest.
        """

        self.current_version = current_version
        self.asset_pattern = asset_pattern
        self.checksums_name = checksums_name

        # GitHub releases API endpoint returning the single latest published release
        # for this repository. The JSON response exposes the release's `tag_name`
        # (the version), `html_url` (the human-facing release page) and `assets`
        # (the files published alongside it).
        self.latest_release_url = (
            f"https://api.github.com/repos/{repo}/releases/latest"
        )

        # Why the most recent check failed, as one of the CHECK_ERROR_* values, or
        # None while no check has failed. Set on every call to check_for_update().
        self.last_error: str | None = None

    ###########################################################################
    ###                UpdateChecker -> check_for_update()                  ###
    ###########################################################################
    def check_for_update(self) -> UpdateCheckResult | None:
        """
        Fetches the latest published release from GitHub and compares it to the
        running version.

        The check fails silently: any network, HTTP, or parsing problem returns
        None rather than raising, so a background check (e.g. on startup) never
        interrupts the user just because they are offline or GitHub is unreachable.
        Why it failed is recorded in last_error for a caller that wants to word its
        message accordingly.

        Returns:
            UpdateCheckResult | None: The comparison outcome and release details, or
                None if the latest release could not be retrieved or parsed.
        """

        self.last_error = None

        try:
            request = urllib.request.Request(
                self.latest_release_url, headers=REQUEST_HEADERS
            )

            with urllib.request.urlopen(
                request, timeout=REQUEST_TIMEOUT_SECONDS
            ) as response:
                release = json.loads(response.read())

            # Normalize the latest tag so a leading "v" (used inconsistently across
            # release tags) never skews the comparison or the displayed version.
            latest_version = release["tag_name"].lstrip("vV")
            release_url = release["html_url"]

            update_available = (
                compare_versions(latest_version, self.current_version) > 0
            )

            assets = release.get("assets") or []

            return UpdateCheckResult(
                update_available,
                latest_version,
                release_url,
                self._find_asset(assets, self.asset_pattern),
                self._find_asset(assets, self.checksums_name),
            )
        except urllib.error.HTTPError as error:
            # GitHub answered, but with a status instead of a release. Caught ahead
            # of URLError (its base class) so a rate-limited check is not filed as a
            # network failure, which is the one thing it is not.
            return self._fail(
                CHECK_ERROR_RATE_LIMITED
                if self._is_rate_limited(error)
                else CHECK_ERROR_HTTP
            )
        except (urllib.error.URLError, OSError):
            # GitHub was never reached: no route, DNS failure, refused connection or
            # a request that outran REQUEST_TIMEOUT_SECONDS.
            return self._fail(CHECK_ERROR_NETWORK)
        except (ValueError, KeyError):
            # ValueError: malformed JSON. KeyError: an unexpected response shape
            # missing the fields we rely on.
            return self._fail(CHECK_ERROR_RESPONSE)

    ###########################################################################
    ###                  UpdateChecker -> _is_rate_limited()                ###
    ###########################################################################
    @staticmethod
    def _is_rate_limited(error: urllib.error.HTTPError) -> bool:
        """
        Reports whether an HTTP failure is GitHub refusing the request for rate
        limiting rather than for some other reason.

        A 403 alone does not prove it: GitHub answers an exhausted budget and an
        ordinary refusal with the same status. The rate-limited one is the one that
        also reports no requests remaining, or says when to come back. A 429 is only
        ever a rate limit and carries neither header reliably.

        Args:
            error (urllib.error.HTTPError): The failure GitHub answered with.

        Returns:
            bool: True if the request was rejected for rate limiting.
        """

        if error.code == TOO_MANY_REQUESTS_STATUS:
            return True

        if error.code != FORBIDDEN_STATUS:
            return False

        # An HTTPError built without a response carries no headers at all.
        headers = getattr(error, "headers", None) or {}

        return headers.get("X-RateLimit-Remaining") == "0" or "Retry-After" in headers

    ###########################################################################
    ###                       UpdateChecker -> _fail()                      ###
    ###########################################################################
    def _fail(self, reason: str) -> None:
        """
        Records why the check failed and yields the silent failure the caller sees.

        Args:
            reason (str): One of the CHECK_ERROR_* values.

        Returns:
            None: Always, so an except block can `return self._fail(...)`.
        """

        self.last_error = reason
        return None

    ###########################################################################
    ###                    UpdateChecker -> _find_asset()                   ###
    ###########################################################################
    def _find_asset(self, assets: list, pattern: str | None) -> ReleaseAsset | None:
        """
        Picks the first published asset whose filename matches a pattern.

        A release publishing no matching asset is an ordinary outcome rather than
        an error: older releases predate the assets this looks for, and a caller
        that injected no pattern wants no installer at all. Both yield None, which
        is what makes the consumer fall back to the manual download flow.

        Args:
            assets (list): The release's "assets" array from the GitHub API.
            pattern (str | None): An fnmatch pattern naming the wanted asset, or
                None to match nothing.

        Returns:
            ReleaseAsset | None: The matching asset, or None if there is none.
        """

        if not pattern:
            return None

        for asset in assets:
            name = asset.get("name", "")
            if fnmatch.fnmatch(name, pattern):
                return ReleaseAsset(
                    name, asset["browser_download_url"], asset.get("size")
                )

        return None
