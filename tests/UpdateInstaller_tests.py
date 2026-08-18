import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from fishbowl_common.UpdateInstaller import (
    UpdateInstaller,
    RELAUNCH_ARG,
    SILENT_ARGS,
)

# Installer the tests launch, and where its log would be written. Nothing is
# executed - subprocess is mocked throughout - so neither path has to exist.
_INSTALLER = Path("/tmp/fishbowl-update/App_Setup.exe")
_LOG_PATH = Path("/tmp/fishbowl-update/App_Setup_install.log")


###############################################################################
###                    UpdateInstaller -> Test Fixture                      ###
###############################################################################
@pytest.fixture
def installer():
    """
    Builds an UpdateInstaller. It has no collaborators to inject: it reaches the
    operating system through subprocess, which each test patches at its point of
    use, so no process is ever started.

    Returns:
        UpdateInstaller: The installer under test.
    """

    yield UpdateInstaller()


###############################################################################
###                    UpdateInstaller -> Test Helpers                      ###
###############################################################################
def _fake_subprocess(**flags):
    """
    Builds a stand-in for the subprocess module carrying only the attributes named,
    so a test can decide whether the Windows-only creation flags exist at all.

    Args:
        **flags: Creation-flag constants to expose, e.g. DETACHED_PROCESS=8.

    Returns:
        types.SimpleNamespace: The stand-in module, whose Popen is a MagicMock.
    """

    return SimpleNamespace(Popen=MagicMock(), **flags)


###############################################################################
###                 Tests UpdateInstaller -> is_supported()                 ###
###############################################################################
def test_is_supported_is_true_on_windows():
    """
    Verifies that Windows - the platform the Inno Setup installer is built for - is
    reported as able to install an update in place.
    """

    with patch("fishbowl_common.UpdateInstaller.sys.platform", "win32"):
        assert UpdateInstaller.is_supported() is True


def test_is_supported_is_false_off_windows():
    """
    Verifies that any other platform is reported as unsupported, so a consumer keeps
    offering the manual download rather than trying to run a Windows executable.
    """

    with patch("fishbowl_common.UpdateInstaller.sys.platform", "linux"):
        assert UpdateInstaller.is_supported() is False


###############################################################################
###                    Tests UpdateInstaller -> launch()                    ###
###############################################################################
@patch("fishbowl_common.UpdateInstaller.subprocess.Popen")
def test_launch_runs_the_installer_silently_and_asks_for_a_relaunch(
    mock_popen, installer
):
    """
    Verifies that the installer is invoked with the unattended switches and the
    relaunch parameter, which is what brings the application back after an upgrade
    the user started from inside it.

    Args:
        mock_popen (unittest.mock.MagicMock): Mocks subprocess.Popen
        installer (pytest.fixture): Provides the installer under test
    """

    assert installer.launch(_INSTALLER) is True

    command = mock_popen.call_args.args[0]
    assert command[0] == str(_INSTALLER)
    assert command[1:] == [*SILENT_ARGS, RELAUNCH_ARG]


@patch("fishbowl_common.UpdateInstaller.subprocess.Popen")
def test_launch_passes_a_log_path_when_one_is_given(mock_popen, installer):
    """
    Verifies that a log path is handed to the installer as its /LOG switch, so a
    silent upgrade that goes wrong leaves something to read afterwards.

    Args:
        mock_popen (unittest.mock.MagicMock): Mocks subprocess.Popen
        installer (pytest.fixture): Provides the installer under test
    """

    installer.launch(_INSTALLER, _LOG_PATH)

    assert mock_popen.call_args.args[0][-1] == f"/LOG={_LOG_PATH}"


@patch("fishbowl_common.UpdateInstaller.subprocess.Popen")
def test_launch_omits_the_log_switch_when_no_path_is_given(mock_popen, installer):
    """
    Verifies that no /LOG switch is passed when the caller wants no log, rather than
    one pointing at nothing.

    Args:
        mock_popen (unittest.mock.MagicMock): Mocks subprocess.Popen
        installer (pytest.fixture): Provides the installer under test
    """

    installer.launch(_INSTALLER)

    assert not any(
        argument.startswith("/LOG=") for argument in mock_popen.call_args.args[0]
    )


@patch("fishbowl_common.UpdateInstaller.subprocess.Popen")
def test_launch_does_not_wait_for_the_installer(mock_popen, installer):
    """
    Verifies that the installer is started and left running rather than waited on.
    The application exits moments later, and the installer only begins its work once
    that has happened - waiting here would deadlock the two against each other.

    Args:
        mock_popen (unittest.mock.MagicMock): Mocks subprocess.Popen
        installer (pytest.fixture): Provides the installer under test
    """

    installer.launch(_INSTALLER)

    mock_popen.return_value.wait.assert_not_called()
    mock_popen.return_value.communicate.assert_not_called()


def test_launch_detaches_the_installer_from_this_process(installer):
    """
    Verifies that the Windows creation flags detaching the child are composed into
    the call, so the installer survives the application it is replacing.

    Args:
        installer (pytest.fixture): Provides the installer under test
    """

    fake_subprocess = _fake_subprocess(
        DETACHED_PROCESS=8, CREATE_NEW_PROCESS_GROUP=512
    )

    with patch("fishbowl_common.UpdateInstaller.subprocess", fake_subprocess):
        installer.launch(_INSTALLER)

    assert fake_subprocess.Popen.call_args.kwargs["creationflags"] == 520
    assert fake_subprocess.Popen.call_args.kwargs["close_fds"] is True


def test_launch_falls_back_to_no_flags_where_they_do_not_exist(installer):
    """
    Verifies that the creation flags resolve to 0 on a platform that does not define
    them. They are Windows-only constants, and this module is imported (and these
    tests run) on Linux too, so reading them by name would break the import there.

    Args:
        installer (pytest.fixture): Provides the installer under test
    """

    fake_subprocess = _fake_subprocess()

    with patch("fishbowl_common.UpdateInstaller.subprocess", fake_subprocess):
        installer.launch(_INSTALLER)

    assert fake_subprocess.Popen.call_args.kwargs["creationflags"] == 0


@patch("fishbowl_common.UpdateInstaller.subprocess.Popen")
def test_launch_returns_false_when_the_installer_cannot_be_started(
    mock_popen, installer
):
    """
    Verifies that an installer that will not start is reported rather than raising,
    so the caller falls back to the manual download instead of exiting for an
    upgrade that is not going to happen.

    Args:
        mock_popen (unittest.mock.MagicMock): Mocks subprocess.Popen
        installer (pytest.fixture): Provides the installer under test
    """

    mock_popen.side_effect = OSError("not executable")

    assert installer.launch(_INSTALLER) is False
