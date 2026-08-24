import hashlib
import pytest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from fishbowl_common.UpdateDownloader import (
    UpdateDownloader,
    CHUNK_SIZE,
    DOWNLOAD_ERROR_DIGEST,
    DOWNLOAD_ERROR_HTTP,
    DOWNLOAD_ERROR_IO,
    DOWNLOAD_ERROR_NETWORK,
    DOWNLOAD_ERROR_NO_DIGEST,
    DOWNLOAD_ERROR_SIZE,
    DOWNLOAD_TIMEOUT_SECONDS,
)

# Asset the tests download, and the URLs they download it from. Nothing is
# fetched - urlopen is mocked throughout - so any values work.
_ASSET_NAME = "App_Setup.exe"
_ASSET_URL = "https://example.com/App_Setup.exe"
_CHECKSUMS_URL = "https://example.com/SHA256SUMS.txt"

# Payload the mocked responses deliver, split so more than one chunk arrives.
_CHUNKS = (b"installer-", b"bytes")
_PAYLOAD = b"".join(_CHUNKS)
_PAYLOAD_SHA256 = hashlib.sha256(_PAYLOAD).hexdigest()


###############################################################################
###                   UpdateDownloader -> Test Fixture                      ###
###############################################################################
@pytest.fixture
def downloader():
    """
    Builds an UpdateDownloader with a mock destination path, so a test can assert
    on how a failed download is cleaned up without a real file ever existing. The
    downloader itself has no collaborators to inject: it reaches the network and the
    disk through urllib and open, both patched per test at their point of use.

    Returns:
        types.SimpleNamespace: Holds the downloader under test (`downloader`) and
            the mock path it writes to (`destination`).
    """

    yield SimpleNamespace(
        downloader=UpdateDownloader(),
        destination=MagicMock(spec=Path),
    )


###############################################################################
###                   UpdateDownloader -> Test Helpers                      ###
###############################################################################
def _http_error(url, code=403):
    """
    Builds the HTTPError urlopen raises when the host answers with a status instead
    of the file - a filtering proxy refusing the transfer, or an asset withdrawn
    from the release.

    Args:
        url (str): The URL the request was made to.
        code (int): The HTTP status answered with.

    Returns:
        urllib.error.HTTPError: The error to raise from the mocked urlopen.
    """

    return urllib.error.HTTPError(url, code, "refused", None, None)


def _sent_headers(mock_urlopen):
    """
    Reads back the headers the mocked urlopen was handed, lowering the names since
    urllib.request.Request title-cases whatever it is given.

    Args:
        mock_urlopen (unittest.mock.MagicMock): The mocked urllib.request.urlopen.

    Returns:
        dict: The request's headers, keyed by lowercased name.
    """

    request = mock_urlopen.call_args.args[0]

    return {name.lower(): value for name, value in request.header_items()}


def _download_response(chunks=_CHUNKS, content_length="15"):
    """
    Builds a mock object mimicking the context manager returned by
    urllib.request.urlopen for a file download, whose read(n) yields the given
    chunks and then the empty bytes that end the transfer.

    Args:
        chunks (tuple): The chunks read() should yield, in order.
        content_length (str | None): What the response reports as its
            Content-Length header, or None for a response that reports none.

    Returns:
        unittest.mock.MagicMock: A mock suitable as urlopen's return value, usable
            in a `with` statement.
    """

    mock_response = MagicMock()
    mock_response.read.side_effect = list(chunks) + [b""]
    mock_response.headers.get.return_value = content_length

    # The object bound by `with urllib.request.urlopen(...) as response`
    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_response
    return mock_context


def _text_response(text: str):
    """
    Builds a mock object mimicking the context manager returned by
    urllib.request.urlopen for a text document, whose read() yields that document.

    Args:
        text (str): The document body the response should deliver.

    Returns:
        unittest.mock.MagicMock: A mock suitable as urlopen's return value, usable
            in a `with` statement.
    """

    mock_response = MagicMock()
    mock_response.read.return_value = text.encode()

    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_response
    return mock_context


###############################################################################
###            Tests UpdateDownloader -> fetch_expected_sha256()            ###
###############################################################################
@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_fetch_expected_sha256_returns_the_digest_published_for_the_asset(
    mock_urlopen, downloader
):
    """
    Verifies that the digest is read from the line naming this asset, not merely the
    first line of the file, so a release publishing several assets verifies the
    right one.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.return_value = _text_response(
        f"{'a' * 64}  App.zip\n{_PAYLOAD_SHA256}  {_ASSET_NAME}\n"
    )

    digest = downloader.downloader.fetch_expected_sha256(_CHECKSUMS_URL, _ASSET_NAME)

    assert digest == _PAYLOAD_SHA256
    mock_urlopen.assert_called_once()
    assert mock_urlopen.call_args.args[0].full_url == _CHECKSUMS_URL
    assert mock_urlopen.call_args.kwargs == {"timeout": DOWNLOAD_TIMEOUT_SECONDS}


@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_fetch_expected_sha256_identifies_itself(mock_urlopen, downloader):
    """
    Verifies that the checksums request carries a User-Agent naming this package.
    The default "Python-urllib" is what the filtering proxies these apps run behind
    refuse, and a refused checksums fetch stops the install before it starts.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.return_value = _text_response(f"{_PAYLOAD_SHA256}  {_ASSET_NAME}\n")

    downloader.downloader.fetch_expected_sha256(_CHECKSUMS_URL, _ASSET_NAME)

    assert _sent_headers(mock_urlopen)["user-agent"] == "fishbowl-common"


@patch("fishbowl_common.UpdateDownloader.open")
@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_download_identifies_itself(mock_urlopen, _mock_open, downloader):
    """
    Verifies that the installer download carries the same User-Agent as the check
    and the checksums fetch, so the whole flow is identifiable rather than only the
    request that opens it.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        _mock_open (unittest.mock.MagicMock): Mocks the builtin open
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.return_value = _download_response()

    downloader.downloader.download(
        _ASSET_URL, downloader.destination, _PAYLOAD_SHA256
    )

    assert _sent_headers(mock_urlopen)["user-agent"] == "fishbowl-common"


@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_fetch_expected_sha256_accepts_the_binary_mode_marker(
    mock_urlopen, downloader
):
    """
    Verifies that the "*" a binary-mode sha256sum entry carries in front of the
    filename does not stop the entry being matched - which is how the tool writes
    the file on Windows.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.return_value = _text_response(
        f"{_PAYLOAD_SHA256} *{_ASSET_NAME}\n"
    )

    assert (
        downloader.downloader.fetch_expected_sha256(_CHECKSUMS_URL, _ASSET_NAME)
        == _PAYLOAD_SHA256
    )


@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_fetch_expected_sha256_lowercases_the_published_digest(
    mock_urlopen, downloader
):
    """
    Verifies that an uppercase digest is normalized, since the comparison it feeds
    is against hexdigest()'s lowercase output.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.return_value = _text_response(
        f"{_PAYLOAD_SHA256.upper()}  {_ASSET_NAME}\n"
    )

    assert (
        downloader.downloader.fetch_expected_sha256(_CHECKSUMS_URL, _ASSET_NAME)
        == _PAYLOAD_SHA256
    )


@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_fetch_expected_sha256_skips_lines_that_are_not_digest_entries(
    mock_urlopen, downloader
):
    """
    Verifies that a blank line, a comment, or an entry whose first field is not a
    digest is passed over rather than mistaken for one.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.return_value = _text_response(
        f"\n# generated by the release workflow\n"
        f"nonsense  {_ASSET_NAME}\n"
        f"{_PAYLOAD_SHA256}  {_ASSET_NAME}\n"
    )

    assert (
        downloader.downloader.fetch_expected_sha256(_CHECKSUMS_URL, _ASSET_NAME)
        == _PAYLOAD_SHA256
    )


@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_fetch_expected_sha256_returns_none_when_the_asset_is_not_listed(
    mock_urlopen, downloader
):
    """
    Verifies that a checksums file listing nothing for this asset yields None, which
    is what stops an unverifiable installer from ever being downloaded.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.return_value = _text_response(f"{_PAYLOAD_SHA256}  App.zip\n")

    assert (
        downloader.downloader.fetch_expected_sha256(_CHECKSUMS_URL, _ASSET_NAME)
        is None
    )
    assert downloader.downloader.last_error == DOWNLOAD_ERROR_NO_DIGEST


@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_fetch_expected_sha256_returns_none_on_network_error(
    mock_urlopen, downloader
):
    """
    Verifies that a network failure is swallowed and reported as None rather than
    raising, matching how every other class in this package reports a problem.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.side_effect = urllib.error.URLError("no network")

    assert (
        downloader.downloader.fetch_expected_sha256(_CHECKSUMS_URL, _ASSET_NAME)
        is None
    )
    assert downloader.downloader.last_error == DOWNLOAD_ERROR_NETWORK


@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_fetch_expected_sha256_separates_a_refusal_from_being_offline(
    mock_urlopen, downloader
):
    """
    Verifies that a host answering with a status - a proxy blocking the transfer,
    or an asset withdrawn from the release - is recorded as an HTTP failure. HTTPError
    subclasses URLError, so without its own clause it would be reported as an
    unreachable network, which is the one thing it is not.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.side_effect = _http_error(_CHECKSUMS_URL)

    assert (
        downloader.downloader.fetch_expected_sha256(_CHECKSUMS_URL, _ASSET_NAME)
        is None
    )
    assert downloader.downloader.last_error == DOWNLOAD_ERROR_HTTP


@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_fetch_expected_sha256_reports_an_unreadable_response(
    mock_urlopen, downloader
):
    """
    Verifies that a socket error raised outside URLError is reported as an I/O
    failure rather than escaping into the worker thread.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.side_effect = OSError("connection reset by peer")

    assert (
        downloader.downloader.fetch_expected_sha256(_CHECKSUMS_URL, _ASSET_NAME)
        is None
    )
    assert downloader.downloader.last_error == DOWNLOAD_ERROR_IO


@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_fetch_expected_sha256_clears_the_error_once_a_fetch_succeeds(
    mock_urlopen, downloader
):
    """
    Verifies that a successful fetch leaves no error behind, so the coordinator -
    which fetches and downloads through one downloader - cannot report a failure
    that has since resolved itself.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.side_effect = urllib.error.URLError("no network")
    downloader.downloader.fetch_expected_sha256(_CHECKSUMS_URL, _ASSET_NAME)

    mock_urlopen.side_effect = None
    mock_urlopen.return_value = _text_response(f"{_PAYLOAD_SHA256}  {_ASSET_NAME}\n")

    assert downloader.downloader.fetch_expected_sha256(_CHECKSUMS_URL, _ASSET_NAME)
    assert downloader.downloader.last_error is None


###############################################################################
###                   Tests UpdateDownloader -> download()                  ###
###############################################################################
@patch("fishbowl_common.UpdateDownloader.open")
@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_download_writes_the_asset_and_returns_it_when_verified(
    mock_urlopen, mock_open, downloader
):
    """
    Verifies that a download matching its published size and digest is written to
    the destination, chunk by chunk, and handed back to the caller.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        mock_open (unittest.mock.MagicMock): Mocks the builtin open
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.return_value = _download_response()

    result = downloader.downloader.download(
        _ASSET_URL,
        downloader.destination,
        _PAYLOAD_SHA256,
        len(_PAYLOAD),
    )

    assert result is downloader.destination
    mock_urlopen.assert_called_once()
    assert mock_urlopen.call_args.args[0].full_url == _ASSET_URL
    assert mock_urlopen.call_args.kwargs == {"timeout": DOWNLOAD_TIMEOUT_SECONDS}
    mock_open.assert_called_once_with(downloader.destination, "wb")

    # The body is written as it arrives rather than buffered whole, which is what
    # keeps a multi-megabyte installer off the heap
    written = mock_open.return_value.__enter__.return_value.write
    assert [call.args[0] for call in written.call_args_list] == list(_CHUNKS)
    downloader.destination.unlink.assert_not_called()


@patch("fishbowl_common.UpdateDownloader.open")
@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_download_reads_the_body_in_chunks(mock_urlopen, _mock_open, downloader):
    """
    Verifies that the response is read a chunk at a time, since a single read() of
    the whole body would leave the progress callback with nothing to report until
    the transfer had already finished.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        _mock_open (unittest.mock.MagicMock): Mocks the builtin open
        downloader (pytest.fixture): Provides the downloader under test
    """

    response = _download_response()
    mock_urlopen.return_value = response

    downloader.downloader.download(
        _ASSET_URL, downloader.destination, _PAYLOAD_SHA256
    )

    read = response.__enter__.return_value.read
    assert read.call_args_list[0].args == (CHUNK_SIZE,)


@patch("fishbowl_common.UpdateDownloader.open")
@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_download_reports_progress_as_the_transfer_advances(
    mock_urlopen, _mock_open, downloader
):
    """
    Verifies that progress is reported once before the first chunk and once after
    each one, against the total the response declares - the sequence a progress bar
    is drawn from.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        _mock_open (unittest.mock.MagicMock): Mocks the builtin open
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.return_value = _download_response(content_length="15")
    progress = MagicMock()

    downloader.downloader.download(
        _ASSET_URL,
        downloader.destination,
        _PAYLOAD_SHA256,
        progress=progress,
    )

    assert [call.args for call in progress.call_args_list] == [
        (0, 15),
        (10, 15),
        (15, 15),
    ]


@patch("fishbowl_common.UpdateDownloader.open")
@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_download_falls_back_to_the_published_size_on_an_unreadable_header(
    mock_urlopen, _mock_open, downloader
):
    """
    Verifies that a Content-Length that is not a number falls back to the published
    size rather than failing a download that is otherwise perfectly good.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        _mock_open (unittest.mock.MagicMock): Mocks the builtin open
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.return_value = _download_response(content_length="unknown")
    progress = MagicMock()

    result = downloader.downloader.download(
        _ASSET_URL,
        downloader.destination,
        _PAYLOAD_SHA256,
        len(_PAYLOAD),
        progress,
    )

    assert result is downloader.destination
    assert progress.call_args_list[0].args == (0, 15)


@patch("fishbowl_common.UpdateDownloader.open")
@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_download_falls_back_to_the_published_size_for_progress(
    mock_urlopen, _mock_open, downloader
):
    """
    Verifies that a response reporting no Content-Length still yields a total to
    measure progress against, taken from the size the release published.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        _mock_open (unittest.mock.MagicMock): Mocks the builtin open
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.return_value = _download_response(content_length=None)
    progress = MagicMock()

    downloader.downloader.download(
        _ASSET_URL,
        downloader.destination,
        _PAYLOAD_SHA256,
        len(_PAYLOAD),
        progress,
    )

    assert [call.args for call in progress.call_args_list] == [
        (0, 15),
        (10, 15),
        (15, 15),
    ]


@patch("fishbowl_common.UpdateDownloader.open")
@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_download_reports_a_zero_total_when_no_size_is_known(
    mock_urlopen, _mock_open, downloader
):
    """
    Verifies that a transfer whose size neither the response nor the release
    declares reports a total of 0, so the caller can tell an unknown length from a
    finished one rather than being handed a division to fail on.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        _mock_open (unittest.mock.MagicMock): Mocks the builtin open
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.return_value = _download_response(content_length=None)
    progress = MagicMock()

    downloader.downloader.download(
        _ASSET_URL, downloader.destination, _PAYLOAD_SHA256, progress=progress
    )

    assert [call.args for call in progress.call_args_list] == [
        (0, 0),
        (10, 0),
        (15, 0),
    ]


@patch("fishbowl_common.UpdateDownloader.open")
@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_download_discards_and_returns_none_on_a_digest_mismatch(
    mock_urlopen, _mock_open, downloader
):
    """
    Verifies that a file hashing to anything other than the published digest is
    deleted and reported as a failure. This is the check the whole feature rests on:
    the file is about to be executed, so it must be provably the one the release
    published.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        _mock_open (unittest.mock.MagicMock): Mocks the builtin open
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.return_value = _download_response()

    result = downloader.downloader.download(
        _ASSET_URL, downloader.destination, "b" * 64
    )

    assert result is None
    assert downloader.downloader.last_error == DOWNLOAD_ERROR_DIGEST
    downloader.destination.unlink.assert_called_once_with(missing_ok=True)


@patch("fishbowl_common.UpdateDownloader.open")
@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_download_discards_and_returns_none_on_a_size_mismatch(
    mock_urlopen, _mock_open, downloader
):
    """
    Verifies that a transfer that ended at the wrong length is deleted and reported
    as a failure, so a connection cut short is caught as the truncation it is.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        _mock_open (unittest.mock.MagicMock): Mocks the builtin open
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.return_value = _download_response()

    result = downloader.downloader.download(
        _ASSET_URL, downloader.destination, _PAYLOAD_SHA256, len(_PAYLOAD) + 1
    )

    assert result is None
    assert downloader.downloader.last_error == DOWNLOAD_ERROR_SIZE
    downloader.destination.unlink.assert_called_once_with(missing_ok=True)


@patch("fishbowl_common.UpdateDownloader.open")
@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_download_discards_and_returns_none_when_the_connection_drops(
    mock_urlopen, _mock_open, downloader
):
    """
    Verifies that a connection failing part-way through leaves no partial file
    behind and is reported as a failure rather than raising into the worker thread.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        _mock_open (unittest.mock.MagicMock): Mocks the builtin open
        downloader (pytest.fixture): Provides the downloader under test
    """

    response = _download_response()
    response.__enter__.return_value.read.side_effect = [
        _CHUNKS[0],
        urllib.error.URLError("connection reset"),
    ]
    mock_urlopen.return_value = response

    result = downloader.downloader.download(
        _ASSET_URL, downloader.destination, _PAYLOAD_SHA256
    )

    assert result is None
    assert downloader.downloader.last_error == DOWNLOAD_ERROR_NETWORK
    downloader.destination.unlink.assert_called_once_with(missing_ok=True)


@patch("fishbowl_common.UpdateDownloader.open")
@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_download_discards_and_reports_a_refusal_as_an_http_failure(
    mock_urlopen, _mock_open, downloader
):
    """
    Verifies that a host refusing the transfer outright is discarded like any other
    failure and recorded as an HTTP failure, so a proxy block is not reported to the
    user as being offline.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        _mock_open (unittest.mock.MagicMock): Mocks the builtin open
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.side_effect = _http_error(_ASSET_URL)

    result = downloader.downloader.download(
        _ASSET_URL, downloader.destination, _PAYLOAD_SHA256
    )

    assert result is None
    assert downloader.downloader.last_error == DOWNLOAD_ERROR_HTTP
    downloader.destination.unlink.assert_called_once_with(missing_ok=True)


@patch("fishbowl_common.UpdateDownloader.open")
@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_download_clears_the_error_once_a_download_succeeds(
    mock_urlopen, _mock_open, downloader
):
    """
    Verifies that a verified download leaves no error behind, so a reused downloader
    cannot report a failure that has since resolved itself.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        _mock_open (unittest.mock.MagicMock): Mocks the builtin open
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.side_effect = _http_error(_ASSET_URL)
    downloader.downloader.download(
        _ASSET_URL, downloader.destination, _PAYLOAD_SHA256
    )

    mock_urlopen.side_effect = None
    mock_urlopen.return_value = _download_response()

    assert (
        downloader.downloader.download(
            _ASSET_URL, downloader.destination, _PAYLOAD_SHA256
        )
        is downloader.destination
    )
    assert downloader.downloader.last_error is None


@patch("fishbowl_common.UpdateDownloader.open")
@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_download_returns_none_when_the_file_cannot_be_written(
    mock_urlopen, mock_open, downloader
):
    """
    Verifies that a disk failure is reported as a failure rather than raising, so a
    full or unwritable temp directory falls back to the manual download.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        mock_open (unittest.mock.MagicMock): Mocks the builtin open
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.return_value = _download_response()
    mock_open.side_effect = OSError("no space left on device")

    assert (
        downloader.downloader.download(
            _ASSET_URL, downloader.destination, _PAYLOAD_SHA256
        )
        is None
    )
    assert downloader.downloader.last_error == DOWNLOAD_ERROR_IO


@patch("fishbowl_common.UpdateDownloader.open")
@patch("fishbowl_common.UpdateDownloader.urllib.request.urlopen")
def test_download_survives_a_cleanup_that_itself_fails(
    mock_urlopen, _mock_open, downloader
):
    """
    Verifies that a delete which cannot be performed does not mask the failure that
    led to it: the caller still gets None rather than an OSError out of the cleanup.

    Args:
        mock_urlopen (unittest.mock.MagicMock): Mocks urllib.request.urlopen
        _mock_open (unittest.mock.MagicMock): Mocks the builtin open
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_urlopen.return_value = _download_response()
    downloader.destination.unlink.side_effect = OSError("file in use")

    assert (
        downloader.downloader.download(
            _ASSET_URL, downloader.destination, "b" * 64
        )
        is None
    )


###############################################################################
###             Tests UpdateDownloader -> default_destination()             ###
###############################################################################
@patch("fishbowl_common.UpdateDownloader.tempfile.mkdtemp")
def test_default_destination_names_the_asset_inside_a_fresh_temp_directory(
    mock_mkdtemp, downloader
):
    """
    Verifies that the download lands under its own temporary directory, keeping the
    installer clear of anything else in the system temp folder.

    Args:
        mock_mkdtemp (unittest.mock.MagicMock): Mocks tempfile.mkdtemp
        downloader (pytest.fixture): Provides the downloader under test
    """

    mock_mkdtemp.return_value = "/tmp/fishbowl-update-abc123"

    destination = downloader.downloader.default_destination(_ASSET_NAME)

    assert destination == Path("/tmp/fishbowl-update-abc123") / _ASSET_NAME
    assert mock_mkdtemp.call_args.kwargs["prefix"].startswith("fishbowl-update")
