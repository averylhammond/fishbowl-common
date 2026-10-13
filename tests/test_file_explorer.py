from pathlib import Path
from unittest.mock import MagicMock, patch

from fishbowl_common.file_explorer import open_in_file_explorer, open_with_default_app

# Where the folder under test resolves to. Nothing touches the filesystem - each
# test hands in a mocked path - so this folder never has to exist.
_RESOLVED_FOLDER = "/srv/fishbowl/Reports"


def _mock_path(is_dir=True, is_file=False):
    """
    Builds a stand-in for a caller's Path whose resolve() returns a second stand-in
    for the absolute path, so a test decides whether a folder or file exists
    without creating one.

    Args:
        is_dir (bool): Whether the resolved path reports itself as an existing folder.
        is_file (bool): Whether the resolved path reports itself as an existing file.

    Returns:
        tuple[unittest.mock.MagicMock, unittest.mock.MagicMock]: The path handed in,
            and the resolved path the launcher should receive.
    """

    resolved = MagicMock(spec=Path)
    resolved.is_dir.return_value = is_dir
    resolved.is_file.return_value = is_file
    resolved.__str__.return_value = _RESOLVED_FOLDER

    path = MagicMock(spec=Path)
    path.resolve.return_value = resolved

    return path, resolved


@patch("fishbowl_common.file_explorer.subprocess.Popen")
@patch("fishbowl_common.file_explorer.os.startfile", create=True)
@patch("fishbowl_common.file_explorer.sys.platform", "win32")
def test_open_in_file_explorer_uses_startfile_on_windows(mock_startfile, mock_popen):
    """
    Verifies that on Windows the resolved folder is handed to os.startfile, and
    that a successful launch is reported as True. startfile is created for the
    test because it exists only on Windows.

    Args:
        mock_startfile (unittest.mock.MagicMock): Mocks os.startfile
        mock_popen (unittest.mock.MagicMock): Mocks subprocess.Popen
    """

    path, resolved = _mock_path()

    assert open_in_file_explorer(path) is True

    mock_startfile.assert_called_once_with(resolved)
    mock_popen.assert_not_called()


@patch("fishbowl_common.file_explorer.subprocess.Popen")
@patch("fishbowl_common.file_explorer.sys.platform", "darwin")
def test_open_in_file_explorer_uses_open_on_macos(mock_popen):
    """
    Verifies that on macOS the resolved folder is opened through the `open` command.

    Args:
        mock_popen (unittest.mock.MagicMock): Mocks subprocess.Popen
    """

    path, _ = _mock_path()

    assert open_in_file_explorer(path) is True

    mock_popen.assert_called_once_with(["open", _RESOLVED_FOLDER])


@patch("fishbowl_common.file_explorer.subprocess.Popen")
@patch("fishbowl_common.file_explorer.sys.platform", "linux")
def test_open_in_file_explorer_uses_xdg_open_elsewhere(mock_popen):
    """
    Verifies that on any other platform the resolved folder is opened through
    xdg-open, the freedesktop launcher mainstream Linux desktops provide.

    Args:
        mock_popen (unittest.mock.MagicMock): Mocks subprocess.Popen
    """

    path, _ = _mock_path()

    assert open_in_file_explorer(path) is True

    mock_popen.assert_called_once_with(["xdg-open", _RESOLVED_FOLDER])


@patch("fishbowl_common.file_explorer.subprocess.Popen")
@patch("fishbowl_common.file_explorer.os.startfile", create=True)
@patch("fishbowl_common.file_explorer.sys.platform", "win32")
def test_open_in_file_explorer_returns_false_when_the_folder_is_missing(mock_startfile, mock_popen):
    """
    Verifies that a path that is not an existing folder (missing, or a file) is
    reported as False without launching anything, so the caller can tell the user
    where it looked. A file is refused too, since the launcher would open the file
    rather than show its folder.

    Args:
        mock_startfile (unittest.mock.MagicMock): Mocks os.startfile
        mock_popen (unittest.mock.MagicMock): Mocks subprocess.Popen
    """

    path, _ = _mock_path(is_dir=False)

    assert open_in_file_explorer(path) is False

    mock_startfile.assert_not_called()
    mock_popen.assert_not_called()


@patch("fishbowl_common.file_explorer.subprocess.Popen", side_effect=FileNotFoundError)
@patch("fishbowl_common.file_explorer.sys.platform", "linux")
def test_open_in_file_explorer_returns_false_when_the_launcher_fails(mock_popen):
    """
    Verifies that an OSError from the launcher (xdg-open not installed, say) is
    reported as False rather than raised into the caller's menu handler.

    Args:
        mock_popen (unittest.mock.MagicMock): Mocks subprocess.Popen, raising
            FileNotFoundError as it does when the command is not installed
    """

    path, _ = _mock_path()

    assert open_in_file_explorer(path) is False

    mock_popen.assert_called_once()


@patch("fishbowl_common.file_explorer.subprocess.Popen")
@patch("fishbowl_common.file_explorer.os.startfile", create=True)
@patch("fishbowl_common.file_explorer.sys.platform", "win32")
def test_open_with_default_app_uses_startfile_on_windows(mock_startfile, mock_popen):
    """
    Verifies that on Windows the resolved file is handed to os.startfile, and that
    a successful launch is reported as True. startfile is created for the test
    because it exists only on Windows.

    Args:
        mock_startfile (unittest.mock.MagicMock): Mocks os.startfile
        mock_popen (unittest.mock.MagicMock): Mocks subprocess.Popen
    """

    path, resolved = _mock_path(is_dir=False, is_file=True)

    assert open_with_default_app(path) is True

    mock_startfile.assert_called_once_with(resolved)
    mock_popen.assert_not_called()


@patch("fishbowl_common.file_explorer.subprocess.Popen")
@patch("fishbowl_common.file_explorer.sys.platform", "darwin")
def test_open_with_default_app_uses_open_on_macos(mock_popen):
    """
    Verifies that on macOS the resolved file is opened through the `open` command.

    Args:
        mock_popen (unittest.mock.MagicMock): Mocks subprocess.Popen
    """

    path, _ = _mock_path(is_dir=False, is_file=True)

    assert open_with_default_app(path) is True

    mock_popen.assert_called_once_with(["open", _RESOLVED_FOLDER])


@patch("fishbowl_common.file_explorer.subprocess.Popen")
@patch("fishbowl_common.file_explorer.sys.platform", "linux")
def test_open_with_default_app_uses_xdg_open_elsewhere(mock_popen):
    """
    Verifies that on any other platform the resolved file is opened through
    xdg-open.

    Args:
        mock_popen (unittest.mock.MagicMock): Mocks subprocess.Popen
    """

    path, _ = _mock_path(is_dir=False, is_file=True)

    assert open_with_default_app(path) is True

    mock_popen.assert_called_once_with(["xdg-open", _RESOLVED_FOLDER])


@patch("fishbowl_common.file_explorer.subprocess.Popen")
@patch("fishbowl_common.file_explorer.os.startfile", create=True)
@patch("fishbowl_common.file_explorer.sys.platform", "win32")
def test_open_with_default_app_returns_false_when_the_file_is_missing(mock_startfile, mock_popen):
    """
    Verifies that a path that is not an existing file (missing, or a folder) is
    reported as False without launching anything. A folder is refused too, since
    the launcher would show it in the file explorer rather than open a file.

    Args:
        mock_startfile (unittest.mock.MagicMock): Mocks os.startfile
        mock_popen (unittest.mock.MagicMock): Mocks subprocess.Popen
    """

    path, _ = _mock_path(is_dir=True, is_file=False)

    assert open_with_default_app(path) is False

    mock_startfile.assert_not_called()
    mock_popen.assert_not_called()


@patch("fishbowl_common.file_explorer.subprocess.Popen", side_effect=FileNotFoundError)
@patch("fishbowl_common.file_explorer.sys.platform", "linux")
def test_open_with_default_app_returns_false_when_the_launcher_fails(mock_popen):
    """
    Verifies that an OSError from the launcher (xdg-open not installed, say) is
    reported as False rather than raised into the caller's menu handler.

    Args:
        mock_popen (unittest.mock.MagicMock): Mocks subprocess.Popen, raising
            FileNotFoundError as it does when the command is not installed
    """

    path, _ = _mock_path(is_dir=False, is_file=True)

    assert open_with_default_app(path) is False

    mock_popen.assert_called_once()
