import os
import subprocess
import sys
from pathlib import Path

# Switches handed to the Inno Setup installer for an unattended upgrade.
# /VERYSILENT and /SUPPRESSMSGBOXES run it with no window and no prompts;
# /NORESTART forbids it rebooting the machine; /CLOSEAPPLICATIONS lets Restart
# Manager close the application if it is still holding its executable open when the
# installer reaches it; /FORCECLOSEAPPLICATIONS lets it terminate what will not
# close gracefully; /NORESTARTAPPLICATIONS stops Restart Manager relaunching what it
# closed, since the relaunch below is the one that must happen.
#
# /FORCECLOSEAPPLICATIONS is not belt and braces. Restart Manager asks an
# application to close by posting to its window, and a PyInstaller onefile build runs
# as two processes whose bootloader owns no window: it never answers, Setup waits out
# its 30-second timeout, and /SUPPRESSMSGBOXES turns the resulting Abort/Retry/Ignore
# prompt into an Abort. The upgrade then rolls back silently, leaving the user on the
# old version with nothing to show for it.
SILENT_ARGS = (
    "/VERYSILENT",
    "/SUPPRESSMSGBOXES",
    "/NORESTART",
    "/CLOSEAPPLICATIONS",
    "/FORCECLOSEAPPLICATIONS",
    "/NORESTARTAPPLICATIONS",
)

# Environment variables PyInstaller's bootloader exports to describe the running
# application's extracted bundle, stripped from what the installer is started with.
# A frozen application passes its whole environment to any child process, and the
# installer passes that on again to the application it relaunches -- which, since
# PyInstaller 6.22.1, refuses to start when it sees them: it takes them to mean it is
# a worker sub-process of a onefile parent and requires its parent process to be the
# same executable, and its parent is the installer. An in-place upgrade leaves the
# path unchanged, so nothing else marks the relaunch as a fresh start.
PYINSTALLER_ENV_PREFIX = "_PYI_"
PYINSTALLER_LEGACY_ENV_VARS = ("_MEIPASS2",)

# Switch asking the installer to start the application again once the upgrade is
# finished. A silent install would otherwise leave the user with no window at all,
# having pressed a button labelled "Update and Restart". The consuming application's
# installer script gates its post-install run on this parameter, so a hand-run
# silent install (someone scripting a deployment) still starts nothing.
RELAUNCH_ARG = "/RELAUNCH=1"


# UpdateInstaller starts a downloaded installer and gets out of its way. The
# installer has to replace the very executable this process is running from, which
# Windows keeps file-locked, so it is launched detached: it must outlive the
# application that started it rather than dying with it.
class UpdateInstaller:

    ###########################################################################
    ###                   UpdateInstaller -> is_supported()                 ###
    ###########################################################################
    @staticmethod
    def is_supported() -> bool:
        """
        Reports whether this platform can install an update in place.

        The installer is a Windows executable built by Inno Setup, so everywhere
        else the caller keeps the manual download flow instead.

        Returns:
            True on Windows, False otherwise.
        """

        return sys.platform == "win32"

    ###########################################################################
    ###                      UpdateInstaller -> launch()                    ###
    ###########################################################################
    def launch(self, installer: Path, log_path: Path | None = None) -> bool:
        """
        Starts the installer detached from this process, silently, asking it to
        relaunch the application when it is done.

        Detaching is what makes the upgrade possible at all: the application exits
        moments after this returns, and a child process would be torn down with it
        before it could replace anything.

        Args:
            installer: The verified installer to run.
            log_path: Where the installer should write its own log, or None to let it
                log nowhere.

        Returns:
            True if the installer was started, False if it could not be.
        """

        command = [str(installer), *SILENT_ARGS, RELAUNCH_ARG]
        if log_path is not None:
            command.append(f"/LOG={log_path}")

        try:
            subprocess.Popen(
                command,
                creationflags=self._detached_flags(),
                close_fds=True,
                env=self._clean_environment(),
            )
        except OSError:
            # A missing, unreadable or non-executable installer: report the failure
            # so the caller can fall back rather than exiting into nothing
            return False

        return True

    ###########################################################################
    ###                UpdateInstaller -> _detached_flags()                ###
    ###########################################################################
    def _detached_flags(self) -> int:
        """
        Builds the process creation flags that detach the installer from this
        application.

        The flags are read with getattr because they exist only on Windows, and
        this module is imported (and its tests run) on Linux too; there they
        resolve to 0, which Popen accepts and ignores.

        Returns:
            The creation flags to hand Popen.
        """

        return getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )

    ###########################################################################
    ###              UpdateInstaller -> _clean_environment()               ###
    ###########################################################################
    def _clean_environment(self) -> dict[str, str]:
        """
        Builds the environment to start the installer with: this process's own,
        less the variables PyInstaller's bootloader exported into it.

        Everything else is passed through untouched, since the installer is
        entitled to the user's real environment -- only the frozen application's
        internals have no business reaching it.

        Returns:
            The environment to hand Popen.
        """

        return {
            name: value
            for name, value in os.environ.items()
            if not name.startswith(PYINSTALLER_ENV_PREFIX)
            and name not in PYINSTALLER_LEGACY_ENV_VARS
        }
