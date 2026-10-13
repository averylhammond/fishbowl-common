import os
import subprocess
import sys
from pathlib import Path


def open_in_file_explorer(path: Path) -> bool:
    """
    Opens a folder in the operating system's file explorer, so the user can see
    what it holds without the application building a browser of its own.

    Opening never raises: a folder that does not exist, a path that is not a
    folder, or a launcher the platform cannot start all return False, and the
    caller decides what to tell the user.

    Args:
        path: The folder to open, absolute or relative to the working directory.

    Returns:
        True if the file explorer was started on the folder, False if it could not be.
    """

    # Resolved so the explorer is handed the same folder the caller means, whatever
    # directory the launched process ends up treating as its own
    folder = path.resolve()

    if not folder.is_dir():
        return False

    return _launch(folder)


def open_with_default_app(path: Path) -> bool:
    """
    Opens a file in the application the operating system associates with its
    type, such as a spreadsheet in Excel, Numbers or LibreOffice.

    Opening never raises: a file that does not exist, a path that is not a file,
    or a launcher the platform cannot start all return False, and the caller
    decides what to tell the user.

    Args:
        path: The file to open, absolute or relative to the working directory.

    Returns:
        True if the default application was started on the file, False if it could not be.
    """

    # Resolved so the application is handed the same file the caller means, whatever
    # directory the launched process ends up treating as its own
    file = path.resolve()

    if not file.is_file():
        return False

    return _launch(file)


def _launch(target: Path) -> bool:
    """
    Hands an existing file or folder to the platform's launcher, which opens it
    the way double-clicking it would.

    Args:
        target: The absolute file or folder to open.

    Returns:
        True if the launcher was started, False if it could not be.
    """

    try:
        # Windows (sys.platform is "win32" on 64-bit Windows too): hand the target
        # to the shell's default action, File Explorer for a folder
        if sys.platform == "win32":
            os.startfile(target)
        # macOS: the `open` command shows a folder in Finder or opens a file in its app
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        # Linux and any other Unix-like OS: xdg-open asks the desktop environment
        # for its default file manager or application
        else:
            subprocess.Popen(["xdg-open", str(target)])
    except OSError:
        # No launcher on this machine (a Linux box without xdg-utils), or one that
        # refused the target: report it rather than letting it reach a menu handler
        return False

    return True
