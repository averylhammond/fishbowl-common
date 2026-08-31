import hashlib
import tempfile
import urllib.error
import urllib.request
from http.client import HTTPResponse
from pathlib import Path
from typing import Callable

from fishbowl_common.UpdateChecker import USER_AGENT

# Cap how long a download may block. It is far longer than the update check's
# timeout because this transfers a whole installer rather than a JSON document, but
# it still bounds a stalled connection instead of hanging the worker thread forever.
DOWNLOAD_TIMEOUT_SECONDS = 30

# How much of the response body to read per iteration. Reading in chunks (rather
# than one read() of the whole body) is what lets the progress callback fire while
# the transfer is still running, and keeps a large installer off the heap.
CHUNK_SIZE = 64 * 1024

# Length of a SHA-256 digest in hexadecimal characters. A line of the checksums
# file whose first field is not one of these is not a digest line.
SHA256_HEX_LENGTH = 64

# Sent with both requests. Only the User-Agent, since these fetch a file rather
# than the API: an Accept pinning a media type would constrain the redirect to the
# asset host for nothing. GitHub documents the User-Agent as required, and the
# filtering proxies these apps are deployed behind routinely refuse the
# "Python-urllib" default.
REQUEST_HEADERS = {"User-Agent": USER_AGENT}

# What UpdateDownloader.last_error carries after a failed fetch or download. The
# calls still fail silently by returning None; this is what lets a caller tell a
# transfer that never started from one that arrived corrupted - and the digest
# mismatch, the one failure worth treating as more than bad luck, from both.
DOWNLOAD_ERROR_HTTP = "http"
DOWNLOAD_ERROR_NETWORK = "network"
DOWNLOAD_ERROR_IO = "io"
DOWNLOAD_ERROR_NO_DIGEST = "no_digest"
DOWNLOAD_ERROR_SIZE = "size"
DOWNLOAD_ERROR_DIGEST = "digest"


# UpdateDownloader fetches a release's installer and proves it is the file the
# release published before anything executes it. Like the rest of this package it
# never raises: every failure - network, disk, a size or digest that does not match
# - comes back as None, so a caller can fall back to the manual download flow.
class UpdateDownloader:

    ###########################################################################
    ###                   UpdateDownloader -> __init__()                    ###
    ###########################################################################
    def __init__(self) -> None:
        """
        Initializes the UpdateDownloader. It takes nothing: every value it works
        from arrives with the call, and it reaches the network and the disk
        directly.
        """

        # Why the most recent fetch or download failed, as one of the
        # DOWNLOAD_ERROR_* values, or None while nothing has failed. Set on every
        # call to fetch_expected_sha256() and download().
        self.last_error: str | None = None

    ###########################################################################
    ###             UpdateDownloader -> fetch_expected_sha256()             ###
    ###########################################################################
    def fetch_expected_sha256(
        self, checksums_url: str, asset_name: str
    ) -> str | None:
        """
        Reads the release's checksums file and returns the digest published for one
        asset.

        The file is the standard sha256sum format - a hex digest, whitespace, then
        the filename, optionally prefixed with "*" to mark a binary-mode entry - so
        it stays verifiable by hand with sha256sum.

        Args:
            checksums_url: Direct download URL of the checksums asset.
            asset_name: Filename of the asset whose digest is wanted.

        Returns:
            The published digest in lowercase hex, or None if the file could not be
            fetched or lists no digest for that asset. Why it failed is recorded in
            last_error.
        """

        self.last_error = None

        try:
            request = urllib.request.Request(checksums_url, headers=REQUEST_HEADERS)

            with urllib.request.urlopen(
                request, timeout=DOWNLOAD_TIMEOUT_SECONDS
            ) as response:
                contents = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError:
            # The host answered with a status instead of the file. Caught ahead of
            # URLError (its base class) so a refusal - a proxy blocking the
            # download, an asset withdrawn from the release - is not filed as an
            # unreachable network.
            return self._fail(DOWNLOAD_ERROR_HTTP)
        except urllib.error.URLError:
            # The host was never reached: no route, DNS failure, refused connection
            # or a request that outran DOWNLOAD_TIMEOUT_SECONDS.
            return self._fail(DOWNLOAD_ERROR_NETWORK)
        except (OSError, ValueError):
            # A socket error raised outside URLError, or a response body that could
            # not be read as expected.
            return self._fail(DOWNLOAD_ERROR_IO)

        for line in contents.splitlines():
            fields = line.split()
            if len(fields) < 2:
                continue

            digest = fields[0]
            if len(digest) != SHA256_HEX_LENGTH:
                continue

            # Compare on the bare filename: the published entry may carry a path
            # or the binary-mode "*" marker in front of it.
            published_name = fields[-1].lstrip("*").replace("\\", "/").split("/")[-1]
            if published_name == asset_name:
                return digest.lower()

        # The file arrived intact and simply does not cover this asset, which is
        # what stops an unverifiable installer from ever being downloaded.
        return self._fail(DOWNLOAD_ERROR_NO_DIGEST)

    ###########################################################################
    ###                    UpdateDownloader -> download()                   ###
    ###########################################################################
    def download(
        self,
        url: str,
        destination: Path,
        expected_sha256: str,
        expected_size: int | None = None,
        progress: Callable[[int, int], None] | None = None,
    ) -> Path | None:
        """
        Downloads a release asset and verifies it against its published size and
        digest.

        Verification happens before this returns, so a caller never executes a file
        that failed it: a mismatched download is deleted rather than left on disk
        for something else to find.

        Args:
            url: Direct download URL of the asset.
            destination: Where to write the downloaded file.
            expected_sha256: The digest the finished file must hash to.
            expected_size: The asset's published size in bytes, checked against what
                actually arrived; None skips the size check.
            progress: Called with the bytes received so far and the total expected, so a
                caller can drive a progress bar. The total is 0 when neither the
                response nor the caller reports one.

        Returns:
            The verified file, or None if the download or either check failed. Why it
            failed is recorded in last_error.
        """

        self.last_error = None
        digest = hashlib.sha256()
        downloaded = 0

        try:
            request = urllib.request.Request(url, headers=REQUEST_HEADERS)

            with urllib.request.urlopen(
                request, timeout=DOWNLOAD_TIMEOUT_SECONDS
            ) as response:
                total = self._response_size(response, expected_size)

                # Report the starting position so a caller can show an empty bar
                # rather than nothing at all while the first chunk is in flight
                if progress is not None:
                    progress(0, total)

                with open(destination, "wb") as downloaded_file:
                    while True:
                        chunk = response.read(CHUNK_SIZE)
                        if not chunk:
                            break

                        downloaded_file.write(chunk)
                        digest.update(chunk)
                        downloaded += len(chunk)

                        if progress is not None:
                            progress(downloaded, total)
        except urllib.error.HTTPError:
            # The host answered with a status instead of the file, so nothing was
            # ever transferred. Caught ahead of URLError, its base class.
            return self._discard_and_fail(destination, DOWNLOAD_ERROR_HTTP)
        except urllib.error.URLError:
            # The host was never reached, or the connection dropped mid-transfer.
            return self._discard_and_fail(destination, DOWNLOAD_ERROR_NETWORK)
        except (OSError, ValueError):
            # The bytes did not make it from the socket to the file: a full or
            # unwritable temp directory, or a socket error raised outside URLError.
            # The two are not separated because both arrive here as a bare OSError,
            # and telling them apart would mean splitting the read/write loop.
            return self._discard_and_fail(destination, DOWNLOAD_ERROR_IO)

        if expected_size is not None and downloaded != expected_size:
            return self._discard_and_fail(destination, DOWNLOAD_ERROR_SIZE)

        if digest.hexdigest() != (expected_sha256 or "").lower():
            return self._discard_and_fail(destination, DOWNLOAD_ERROR_DIGEST)

        return destination

    ###########################################################################
    ###              UpdateDownloader -> default_destination()             ###
    ###########################################################################
    def default_destination(self, asset_name: str) -> Path:
        """
        Builds a path to download an asset to, in a private temporary directory.

        A fresh directory per download keeps the file clear of anything else in the
        system temp folder, and leaves the installer readable after the application
        exits - which it must, since the installer only starts running once the
        application it is replacing is gone.

        Args:
            asset_name: Filename to give the downloaded asset.

        Returns:
            The path to download the asset to.
        """

        return Path(tempfile.mkdtemp(prefix="fishbowl-update-")) / asset_name

    ###########################################################################
    ###                UpdateDownloader -> _response_size()                ###
    ###########################################################################
    def _response_size(
        self, response: HTTPResponse, expected_size: int | None
    ) -> int:
        """
        Determines how many bytes the download is expected to be.

        Args:
            response: The object returned by urlopen, whose headers may carry a
                Content-Length.
            expected_size: The size published for the asset, used when the response does
                not report one.

        Returns:
            The expected total in bytes, or 0 when neither source knows it.
        """

        try:
            content_length = response.headers.get("Content-Length")
            if content_length is not None:
                return int(content_length)
        except (AttributeError, TypeError, ValueError):
            # A response with no headers, or a Content-Length that is not a number:
            # fall back to the published size rather than failing the download
            pass

        return expected_size or 0

    ###########################################################################
    ###                     UpdateDownloader -> _fail()                    ###
    ###########################################################################
    def _fail(self, reason: str) -> None:
        """
        Records why the call failed and yields the silent failure the caller sees.

        Args:
            reason: One of the DOWNLOAD_ERROR_* values.

        Returns:
            Always, so an except block can `return self._fail(...)`.
        """

        self.last_error = reason
        return None

    ###########################################################################
    ###               UpdateDownloader -> _discard_and_fail()              ###
    ###########################################################################
    def _discard_and_fail(self, destination: Path, reason: str) -> None:
        """
        Deletes an unusable download and records why it was unusable, so no failure
        path can record a reason while leaving something runnable on disk.

        Args:
            destination: The file to delete; it need not exist.
            reason: One of the DOWNLOAD_ERROR_* values.

        Returns:
            Always, matching what a failed download returns.
        """

        self._discard(destination)
        return self._fail(reason)

    ###########################################################################
    ###                   UpdateDownloader -> _discard()                   ###
    ###########################################################################
    def _discard(self, destination: Path) -> None:
        """
        Deletes a partial or unverified download, so nothing else can pick it up
        and run it.

        Args:
            destination: The file to delete; it need not exist.
        """

        try:
            destination.unlink(missing_ok=True)
        except OSError:
            # Failing to clean up must not mask the failure that led here
            pass
