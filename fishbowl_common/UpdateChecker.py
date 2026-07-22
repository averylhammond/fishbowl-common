import json
import urllib.error
import urllib.request

# Cap how long the request may block so a slow or unreachable network can never
# stall a caller (e.g. an update check run on application startup).
REQUEST_TIMEOUT_SECONDS = 5


# UpdateCheckResult is a plain data holder describing the outcome of comparing the
# latest published release against the running application version.
class UpdateCheckResult:

    ###########################################################################
    ###                  UpdateCheckResult -> __init__()                    ###
    ###########################################################################
    def __init__(self, update_available: bool, latest_version: str, release_url: str):
        """
        Initializes the UpdateCheckResult with the comparison outcome and the
        details needed to point the user at the new release.

        Args:
            update_available (bool): True if the latest published release is
                strictly newer than the running version.
            latest_version (str): The latest release's version, normalized with any
                leading "v" stripped (e.g. "3.1.0").
            release_url (str): The URL of the latest release's page on GitHub.
        """

        self.update_available = update_available
        self.latest_version = latest_version
        self.release_url = release_url


# UpdateChecker queries the GitHub releases API for the latest published release
# and compares its version against the running application version, so the app can
# tell the user when a newer build is available.
class UpdateChecker:

    ###########################################################################
    ###                    UpdateChecker -> __init__()                      ###
    ###########################################################################
    def __init__(self, current_version: str, repo: str):
        """
        Initializes the UpdateChecker with the version to compare against and the
        repository to check for releases.

        Args:
            current_version (str): The running application's version, injected by the
                caller (typically from its own VERSION constant).
            repo (str): The GitHub repository in "owner/name" form whose latest
                release is compared against current_version.
        """

        self.current_version = current_version

        # GitHub releases API endpoint returning the single latest published release
        # for this repository. The JSON response exposes the release's `tag_name`
        # (the version) and `html_url` (the human-facing release page).
        self.latest_release_url = (
            f"https://api.github.com/repos/{repo}/releases/latest"
        )

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

        Returns:
            UpdateCheckResult | None: The comparison outcome and release details, or
                None if the latest release could not be retrieved or parsed.
        """

        try:
            with urllib.request.urlopen(
                self.latest_release_url, timeout=REQUEST_TIMEOUT_SECONDS
            ) as response:
                release = json.loads(response.read())

            # Normalize the latest tag so a leading "v" (used inconsistently across
            # release tags) never skews the comparison or the displayed version.
            latest_version = release["tag_name"].lstrip("vV")
            release_url = release["html_url"]

            update_available = self._parse_version(latest_version) > self._parse_version(
                self.current_version
            )

            return UpdateCheckResult(update_available, latest_version, release_url)
        except (urllib.error.URLError, OSError, ValueError, KeyError):
            # URLError/OSError: network or HTTP failure. ValueError: malformed JSON
            # or a non-numeric version segment. KeyError: an unexpected response
            # shape missing the fields we rely on.
            return None

    ###########################################################################
    ###                  UpdateChecker -> _parse_version()                  ###
    ###########################################################################
    def _parse_version(self, version: str) -> tuple[int, ...]:
        """
        Parses a version string into a tuple of integers for semantic comparison.

        Comparing the integer tuples (rather than the raw strings) keeps the
        ordering numeric, so "3.10.0" correctly sorts after "3.9.0".

        Args:
            version (str): A dotted version string, optionally prefixed with "v"
                (e.g. "v3.1.0" or "3.1.0").

        Returns:
            tuple[int, ...]: The version's numeric segments, e.g. (3, 1, 0).
        """

        return tuple(int(segment) for segment in version.lstrip("vV").split("."))
