import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from fishbowl_common.UpdateCoordinator import UpdateCoordinator, UpdateDisplay

# Values injected into the coordinator under test. The version is only ever compared
# by UpdateChecker (which is mocked here) and echoed back in the up-to-date message,
# and any "owner/name" repo works since the checker derives its own URL from it.
_TEST_VERSION = "3.1.2"
_TEST_REPO = "owner/repo"

# Installer the release publishes, and the pattern the consuming application would
# have injected to find it.
_INSTALLER_NAME = "App_Setup.exe"
_ASSET_PATTERN = "App_Setup.exe"


###############################################################################
###                    UpdateCoordinator -> Test Fixture                    ###
###############################################################################
@pytest.fixture
def coordinator():
    """
    Builds an UpdateCoordinator with a mock display standing in for the application
    window, so no toolkit is involved and every presentation call is assertable. The
    mock display is built against the UpdateDisplay protocol, so a call to anything
    outside that contract fails the test.

    Returns:
        types.SimpleNamespace: Holds the constructed coordinator (`coordinator`) and
            the mock display it presents through (`display`).
    """

    display = MagicMock(spec=UpdateDisplay)

    yield SimpleNamespace(
        coordinator=UpdateCoordinator(
            current_version=_TEST_VERSION,
            repo=_TEST_REPO,
            display=display,
            asset_pattern=_ASSET_PATTERN,
        ),
        display=display,
    )


###############################################################################
###                    UpdateCoordinator -> Test Helpers                    ###
###############################################################################
def _result(update_available=True, installer=True, checksums=True):
    """
    Builds a stand-in for an UpdateCheckResult, shaped like what UpdateChecker
    returns but without going near the network.

    Args:
        update_available (bool): Whether the release is newer than the running
            version
        installer (bool): Whether the release publishes an installer asset
        checksums (bool): Whether the release publishes a checksums asset

    Returns:
        types.SimpleNamespace: The stand-in result.
    """

    return SimpleNamespace(
        update_available=update_available,
        latest_version="9.9.9",
        release_url="https://example.com/release",
        installer_asset=(
            SimpleNamespace(
                name=_INSTALLER_NAME,
                download_url="https://example.com/App_Setup.exe",
                size=2048,
            )
            if installer
            else None
        ),
        checksums_asset=(
            SimpleNamespace(
                name="SHA256SUMS.txt",
                download_url="https://example.com/SHA256SUMS.txt",
                size=128,
            )
            if checksums
            else None
        ),
    )


###############################################################################
###                   Tests UpdateCoordinator -> start()                    ###
###############################################################################
def test_start_spawns_a_started_daemon_worker_thread(coordinator):
    """
    Verifies that a check runs on a started daemon thread targeting the worker, so
    the GUI never blocks on the GitHub API and a stalled request cannot delay
    application shutdown.

    Args:
        coordinator (pytest.fixture): Provides the coordinator and its mock display
    """

    with patch(
        "fishbowl_common.UpdateCoordinator.threading.Thread"
    ) as mock_thread_cls:
        coordinator.coordinator.start()

    mock_thread_cls.assert_called_once_with(
        target=coordinator.coordinator._run_check, args=(False,), daemon=True
    )
    mock_thread_cls.return_value.start.assert_called_once_with()


def test_start_passes_the_manual_flag_to_the_worker(coordinator):
    """
    Verifies that a manually triggered check forwards the manual flag to the worker
    thread, which is what enables the up-to-date/failure feedback later on.

    Args:
        coordinator (pytest.fixture): Provides the coordinator and its mock display
    """

    with patch(
        "fishbowl_common.UpdateCoordinator.threading.Thread"
    ) as mock_thread_cls:
        coordinator.coordinator.start(manual=True)

    mock_thread_cls.assert_called_once_with(
        target=coordinator.coordinator._run_check, args=(True,), daemon=True
    )


###############################################################################
###                 Tests UpdateCoordinator -> _run_check()                 ###
###############################################################################
def test_run_check_schedules_the_result_on_the_gui_thread(coordinator):
    """
    Verifies that the worker performs the check with the injected version, repo and
    asset pattern, then hands the outcome back through display.after() rather than
    presenting it itself, so the toolkit is only ever touched from the thread that
    owns it.

    Args:
        coordinator (pytest.fixture): Provides the coordinator and its mock display
    """

    with patch(
        "fishbowl_common.UpdateCoordinator.UpdateChecker"
    ) as mock_checker_cls:
        mock_result = mock_checker_cls.return_value.check_for_update.return_value
        coordinator.coordinator._run_check(manual=True)

    # The check is built from the values the consumer injected, not from constants
    mock_checker_cls.assert_called_once_with(
        current_version=_TEST_VERSION, repo=_TEST_REPO, asset_pattern=_ASSET_PATTERN
    )
    mock_checker_cls.return_value.check_for_update.assert_called_once_with()

    # Nothing is presented from the worker thread; the result is marshalled instead
    coordinator.display.after.assert_called_once_with(
        0, coordinator.coordinator._handle_result, mock_result, True
    )
    coordinator.display.show_update_available.assert_not_called()


###############################################################################
###               Tests UpdateCoordinator -> _handle_result()               ###
###############################################################################
@patch("fishbowl_common.UpdateCoordinator.UpdateInstaller")
def test_handle_result_shows_the_update_window_when_newer(
    mock_installer_cls, coordinator
):
    """
    Verifies that a strictly newer release opens the update window on a startup
    check, with no redundant popup alongside it.

    Args:
        mock_installer_cls (unittest.mock.MagicMock): Mocks UpdateInstaller, whose
            is_supported() decides whether an in-place install is offered
        coordinator (pytest.fixture): Provides the coordinator and its mock display
    """

    mock_installer_cls.is_supported.return_value = False
    result = _result()

    coordinator.coordinator._handle_result(result)

    coordinator.display.show_update_available.assert_called_once_with(result, None)
    coordinator.display.show_popup.assert_not_called()


@patch("fishbowl_common.UpdateCoordinator.UpdateInstaller")
def test_handle_result_shows_the_update_window_when_newer_on_a_manual_check(
    mock_installer_cls, coordinator
):
    """
    Verifies that a manual check announces a newer release the same way a startup
    check does, without also reporting an outcome through a popup.

    Args:
        mock_installer_cls (unittest.mock.MagicMock): Mocks UpdateInstaller, whose
            is_supported() decides whether an in-place install is offered
        coordinator (pytest.fixture): Provides the coordinator and its mock display
    """

    mock_installer_cls.is_supported.return_value = False
    result = _result()

    coordinator.coordinator._handle_result(result, manual=True)

    coordinator.display.show_update_available.assert_called_once_with(result, None)
    coordinator.display.show_popup.assert_not_called()


@patch("fishbowl_common.UpdateCoordinator.UpdateInstaller")
def test_handle_result_offers_the_install_when_the_release_can_be_installed(
    mock_installer_cls, coordinator
):
    """
    Verifies that a release publishing both assets, on a platform whose installer it
    is, reaches the window with a callback bound to this result - the callback the
    "Update and Restart" button is built from.

    Args:
        mock_installer_cls (unittest.mock.MagicMock): Mocks UpdateInstaller, whose
            is_supported() decides whether an in-place install is offered
        coordinator (pytest.fixture): Provides the coordinator and its mock display
    """

    mock_installer_cls.is_supported.return_value = True
    result = _result()

    coordinator.coordinator._handle_result(result)

    start_install = coordinator.display.show_update_available.call_args.args[1]
    assert start_install.func == coordinator.coordinator.start_install
    assert start_install.args == (result,)


@pytest.mark.parametrize(
    "installer, checksums, supported",
    [
        (False, True, True),
        (True, False, True),
        (True, True, False),
    ],
)
@patch("fishbowl_common.UpdateCoordinator.UpdateInstaller")
def test_handle_result_withholds_the_install_when_it_cannot_be_offered(
    mock_installer_cls, coordinator, installer, checksums, supported
):
    """
    Verifies that a missing installer asset, a missing checksums asset, or a
    platform this installer is not built for each leaves the window with no install
    callback, so the user is sent to the release page instead. The checksums file is
    as required as the installer: without it the download cannot be proven to be
    what the release published.

    Args:
        mock_installer_cls (unittest.mock.MagicMock): Mocks UpdateInstaller, whose
            is_supported() decides whether an in-place install is offered
        coordinator (pytest.fixture): Provides the coordinator and its mock display
        installer (bool): Whether the release publishes an installer asset
        checksums (bool): Whether the release publishes a checksums asset
        supported (bool): Whether the platform can run the installer
    """

    mock_installer_cls.is_supported.return_value = supported

    coordinator.coordinator._handle_result(
        _result(installer=installer, checksums=checksums)
    )

    assert coordinator.display.show_update_available.call_args.args[1] is None


def test_handle_result_stays_silent_when_up_to_date_on_startup(coordinator):
    """
    Verifies that the startup check says nothing when the running version is already
    the latest, so a launch is never interrupted to report a non-event.

    Args:
        coordinator (pytest.fixture): Provides the coordinator and its mock display
    """

    coordinator.coordinator._handle_result(_result(update_available=False))

    coordinator.display.show_update_available.assert_not_called()
    coordinator.display.show_popup.assert_not_called()


def test_handle_result_stays_silent_when_the_startup_check_fails(coordinator):
    """
    Verifies that a failed startup check (a None result) says nothing, so a user who
    is simply offline is never interrupted on launch.

    Args:
        coordinator (pytest.fixture): Provides the coordinator and its mock display
    """

    coordinator.coordinator._handle_result(None)

    coordinator.display.show_update_available.assert_not_called()
    coordinator.display.show_popup.assert_not_called()


def test_handle_result_reports_up_to_date_on_a_manual_check(coordinator):
    """
    Verifies that a manual check confirms an up-to-date install through a popup
    naming the injected version, so a deliberate action always reports an outcome.

    Args:
        coordinator (pytest.fixture): Provides the coordinator and its mock display
    """

    coordinator.coordinator._handle_result(_result(update_available=False), manual=True)

    coordinator.display.show_popup.assert_called_once()
    assert coordinator.display.show_popup.call_args.args[0] == "No Updates Available"
    assert _TEST_VERSION in coordinator.display.show_popup.call_args.args[1]
    coordinator.display.show_update_available.assert_not_called()


def test_handle_result_reports_failure_on_a_manual_check(coordinator):
    """
    Verifies that a manual check whose fetch failed (a None result) reports that
    failure through a popup rather than silently doing nothing.

    Args:
        coordinator (pytest.fixture): Provides the coordinator and its mock display
    """

    coordinator.coordinator._handle_result(None, manual=True)

    coordinator.display.show_popup.assert_called_once()
    assert coordinator.display.show_popup.call_args.args[0] == "Update Check Failed"
    coordinator.display.show_update_available.assert_not_called()


###############################################################################
###               Tests UpdateCoordinator -> start_install()                ###
###############################################################################
def test_start_install_spawns_a_started_daemon_worker_thread(coordinator):
    """
    Verifies that the download runs on a started daemon thread targeting the install
    worker, so the GUI keeps painting its progress bar while a multi-megabyte
    installer is in flight.

    Args:
        coordinator (pytest.fixture): Provides the coordinator and its mock display
    """

    result = _result()
    on_progress = MagicMock()
    on_finished = MagicMock()

    with patch(
        "fishbowl_common.UpdateCoordinator.threading.Thread"
    ) as mock_thread_cls:
        coordinator.coordinator.start_install(result, on_progress, on_finished)

    mock_thread_cls.assert_called_once_with(
        target=coordinator.coordinator._run_install,
        args=(result, on_progress, on_finished),
        daemon=True,
    )
    mock_thread_cls.return_value.start.assert_called_once_with()


###############################################################################
###                Tests UpdateCoordinator -> _run_install()                ###
###############################################################################
@patch("fishbowl_common.UpdateCoordinator.UpdateInstaller")
@patch("fishbowl_common.UpdateCoordinator.UpdateDownloader")
def test_run_install_verifies_and_starts_the_downloaded_installer(
    mock_downloader_cls, mock_installer_cls, coordinator
):
    """
    Verifies that the worker fetches the published digest for the installer, hands
    the download that digest and the published size to verify against, and starts
    the verified file - reporting success back on the GUI thread.

    Args:
        mock_downloader_cls (unittest.mock.MagicMock): Mocks UpdateDownloader
        mock_installer_cls (unittest.mock.MagicMock): Mocks UpdateInstaller
        coordinator (pytest.fixture): Provides the coordinator and its mock display
    """

    downloader = mock_downloader_cls.return_value
    downloader.fetch_expected_sha256.return_value = "abc123"
    downloaded = Path("/tmp/fishbowl-update/App_Setup.exe")
    downloader.download.return_value = downloaded
    mock_installer_cls.return_value.launch.return_value = True

    result = _result()
    on_finished = MagicMock()

    coordinator.coordinator._run_install(result, MagicMock(), on_finished)

    # The digest is looked up for this asset by name, so a release publishing
    # several files still verifies the right one
    downloader.fetch_expected_sha256.assert_called_once_with(
        result.checksums_asset.download_url, _INSTALLER_NAME
    )

    download_args = downloader.download.call_args.args
    assert download_args[0] == result.installer_asset.download_url
    assert download_args[1] == downloader.default_destination.return_value
    assert download_args[2] == "abc123"
    assert download_args[3] == result.installer_asset.size

    assert mock_installer_cls.return_value.launch.call_args.args[0] == downloaded
    coordinator.display.after.assert_called_once_with(0, on_finished, True)


@patch("fishbowl_common.UpdateCoordinator.UpdateInstaller")
@patch("fishbowl_common.UpdateCoordinator.UpdateDownloader")
def test_run_install_marshals_download_progress_onto_the_gui_thread(
    mock_downloader_cls, mock_installer_cls, coordinator
):
    """
    Verifies that the progress callback handed to the downloader does not touch the
    window directly but routes through display.after(), since it fires on the
    download's worker thread.

    Args:
        mock_downloader_cls (unittest.mock.MagicMock): Mocks UpdateDownloader
        mock_installer_cls (unittest.mock.MagicMock): Mocks UpdateInstaller
        coordinator (pytest.fixture): Provides the coordinator and its mock display
    """

    downloader = mock_downloader_cls.return_value
    downloader.fetch_expected_sha256.return_value = "abc123"
    downloader.download.return_value = Path("/tmp/fishbowl-update/App_Setup.exe")
    mock_installer_cls.return_value.launch.return_value = True

    on_progress = MagicMock()

    coordinator.coordinator._run_install(_result(), on_progress, MagicMock())

    # Fire the callback the downloader was handed, as a transfer in flight would
    downloader.download.call_args.args[4](512, 2048)

    on_progress.assert_not_called()
    coordinator.display.after.assert_any_call(0, on_progress, 512, 2048)


@patch("fishbowl_common.UpdateCoordinator.UpdateInstaller")
@patch("fishbowl_common.UpdateCoordinator.UpdateDownloader")
def test_run_install_reports_failure_when_no_digest_is_published(
    mock_downloader_cls, mock_installer_cls, coordinator
):
    """
    Verifies that a checksums file listing no digest for this asset stops the flow
    before anything is downloaded, since an installer that cannot be verified must
    never be executed.

    Args:
        mock_downloader_cls (unittest.mock.MagicMock): Mocks UpdateDownloader
        mock_installer_cls (unittest.mock.MagicMock): Mocks UpdateInstaller
        coordinator (pytest.fixture): Provides the coordinator and its mock display
    """

    downloader = mock_downloader_cls.return_value
    downloader.fetch_expected_sha256.return_value = None

    on_finished = MagicMock()

    coordinator.coordinator._run_install(_result(), MagicMock(), on_finished)

    downloader.download.assert_not_called()
    mock_installer_cls.return_value.launch.assert_not_called()
    coordinator.display.after.assert_called_once_with(0, on_finished, False)


@patch("fishbowl_common.UpdateCoordinator.UpdateInstaller")
@patch("fishbowl_common.UpdateCoordinator.UpdateDownloader")
def test_run_install_reports_failure_when_the_download_fails(
    mock_downloader_cls, mock_installer_cls, coordinator
):
    """
    Verifies that a download that failed or failed its verification (a None result)
    is never handed to the installer, and is reported so the window can fall back to
    the release page.

    Args:
        mock_downloader_cls (unittest.mock.MagicMock): Mocks UpdateDownloader
        mock_installer_cls (unittest.mock.MagicMock): Mocks UpdateInstaller
        coordinator (pytest.fixture): Provides the coordinator and its mock display
    """

    downloader = mock_downloader_cls.return_value
    downloader.fetch_expected_sha256.return_value = "abc123"
    downloader.download.return_value = None

    on_finished = MagicMock()

    coordinator.coordinator._run_install(_result(), MagicMock(), on_finished)

    mock_installer_cls.return_value.launch.assert_not_called()
    coordinator.display.after.assert_called_once_with(0, on_finished, False)


@patch("fishbowl_common.UpdateCoordinator.UpdateInstaller")
@patch("fishbowl_common.UpdateCoordinator.UpdateDownloader")
def test_run_install_reports_failure_when_the_installer_will_not_start(
    mock_downloader_cls, mock_installer_cls, coordinator
):
    """
    Verifies that an installer that could not be started is reported as a failure,
    so the application falls back rather than exiting for an upgrade that is not
    going to happen.

    Args:
        mock_downloader_cls (unittest.mock.MagicMock): Mocks UpdateDownloader
        mock_installer_cls (unittest.mock.MagicMock): Mocks UpdateInstaller
        coordinator (pytest.fixture): Provides the coordinator and its mock display
    """

    downloader = mock_downloader_cls.return_value
    downloader.fetch_expected_sha256.return_value = "abc123"
    downloader.download.return_value = Path("/tmp/fishbowl-update/App_Setup.exe")
    mock_installer_cls.return_value.launch.return_value = False

    on_finished = MagicMock()

    coordinator.coordinator._run_install(_result(), MagicMock(), on_finished)

    coordinator.display.after.assert_called_once_with(0, on_finished, False)
