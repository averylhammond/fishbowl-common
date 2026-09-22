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

    try:
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])
    except OSError:
        # No launcher on this machine (a Linux box without xdg-utils), or one that
        # refused the folder: report it rather than letting it reach a menu handler
        return False

    return True
