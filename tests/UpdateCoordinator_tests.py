import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from fishbowl_common.UpdateCoordinator import UpdateCoordinator, UpdateDisplay

# Values injected into the coordinator under test. The version is only ever compared
# by UpdateChecker (which is mocked here) and echoed back in the up-to-date message,
# and any "owner/name" repo works since the checker derives its own URL from it.
_TEST_VERSION = "3.1.2"
_TEST_REPO = "owner/repo"


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
            current_version=_TEST_VERSION, repo=_TEST_REPO, display=display
        ),
        display=display,
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
    Verifies that the worker performs the check with the injected version and repo,
    then hands the outcome back through display.after() rather than presenting it
    itself, so the toolkit is only ever touched from the thread that owns it.

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
        current_version=_TEST_VERSION, repo=_TEST_REPO
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
def test_handle_result_shows_the_update_window_when_newer(coordinator):
    """
    Verifies that a strictly newer release opens the update window on a startup
    check, with no redundant popup alongside it.

    Args:
        coordinator (pytest.fixture): Provides the coordinator and its mock display
    """

    result = SimpleNamespace(update_available=True)

    coordinator.coordinator._handle_result(result)

    coordinator.display.show_update_available.assert_called_once_with(result)
    coordinator.display.show_popup.assert_not_called()


def test_handle_result_shows_the_update_window_when_newer_on_a_manual_check(
    coordinator,
):
    """
    Verifies that a manual check announces a newer release the same way a startup
    check does, without also reporting an outcome through a popup.

    Args:
        coordinator (pytest.fixture): Provides the coordinator and its mock display
    """

    result = SimpleNamespace(update_available=True)

    coordinator.coordinator._handle_result(result, manual=True)

    coordinator.display.show_update_available.assert_called_once_with(result)
    coordinator.display.show_popup.assert_not_called()


def test_handle_result_stays_silent_when_up_to_date_on_startup(coordinator):
    """
    Verifies that the startup check says nothing when the running version is already
    the latest, so a launch is never interrupted to report a non-event.

    Args:
        coordinator (pytest.fixture): Provides the coordinator and its mock display
    """

    coordinator.coordinator._handle_result(SimpleNamespace(update_available=False))

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

    coordinator.coordinator._handle_result(
        SimpleNamespace(update_available=False), manual=True
    )

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
