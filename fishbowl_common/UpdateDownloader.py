import hashlib
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

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


# UpdateDownloader fetches a release's installer and proves it is the file the
# release published before anything executes it. Like the rest of this package it
# never raises: every failure - network, disk, a size or digest that does not match
# - comes back as None, so a caller can fall back to the manual download flow.
class UpdateDownloader:

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
            checksums_url (str): Direct download URL of the checksums asset.
            asset_name (str): Filename of the asset whose digest is wanted.

        Returns:
            str | None: The published digest in lowercase hex, or None if the file
                could not be fetched or lists no digest for that asset.
        """

        try:
            with urllib.request.urlopen(
                checksums_url, timeout=DOWNLOAD_TIMEOUT_SECONDS
            ) as response:
                contents = response.read().decode("utf-8", "replace")
        except (urllib.error.URLError, OSError, ValueError):
            # URLError/OSError: network or HTTP failure. ValueError: a response
            # body that is not decodable text.
            return None

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

        return None

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
            url (str): Direct download URL of the asset.
            destination (Path): Where to write the downloaded file.
            expected_sha256 (str): The digest the finished file must hash to.
            expected_size (int | None): The asset's published size in bytes, checked
                against what actually arrived; None skips the size check.
            progress (Callable[[int, int], None] | None): Called with the bytes
                received so far and the total expected, so a caller can drive a
                progress bar. The total is 0 when neither the response nor the
                caller reports one.

        Returns:
            Path | None: The verified file, or None if the download or either check
                failed.
        """

        digest = hashlib.sha256()
        downloaded = 0

        try:
            with urllib.request.urlopen(
                url, timeout=DOWNLOAD_TIMEOUT_SECONDS
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
        except (urllib.error.URLError, OSError, ValueError):
            # URLError/OSError: network, HTTP or disk failure. ValueError: a
            # response whose body could not be read as expected.
            self._discard(destination)
            return None

        if expected_size is not None and downloaded != expected_size:
            self._discard(destination)
            return None

        if digest.hexdigest() != (expected_sha256 or "").lower():
            self._discard(destination)
            return None

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
            asset_name (str): Filename to give the downloaded asset.

        Returns:
            Path: The path to download the asset to.
        """

        return Path(tempfile.mkdtemp(prefix="fishbowl-update-")) / asset_name

    ###########################################################################
    ###                UpdateDownloader -> _response_size()                ###
    ###########################################################################
    def _response_size(self, response, expected_size: int | None) -> int:
        """
        Determines how many bytes the download is expected to be.

        Args:
            response: The object returned by urlopen, whose headers may carry a
                Content-Length.
            expected_size (int | None): The size published for the asset, used when
                the response does not report one.

        Returns:
            int: The expected total in bytes, or 0 when neither source knows it.
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
    ###                   UpdateDownloader -> _discard()                   ###
    ###########################################################################
    def _discard(self, destination: Path) -> None:
        """
        Deletes a partial or unverified download, so nothing else can pick it up
        and run it.

        Args:
            destination (Path): The file to delete; it need not exist.
        """

        try:
            destination.unlink(missing_ok=True)
        except OSError:
            # Failing to clean up must not mask the failure that led here
            pass
