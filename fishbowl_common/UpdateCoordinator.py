import threading
from typing import Protocol

from fishbowl_common.UpdateChecker import UpdateChecker, UpdateCheckResult


# UpdateDisplay describes the narrow slice of an application window the coordinator
# needs. Declaring it as a Protocol (rather than importing a concrete window class)
# is what keeps this module - and with it the headless half of the package - free of
# any tkinter import, even though the object passed in is a Tk window.
class UpdateDisplay(Protocol):

    def after(self, ms: int, func=None, *args) -> str:
        """
        Schedules a callback to run on the GUI thread after a delay.

        Args:
            ms (int): Milliseconds to wait before running the callback.
            func (Callable | None): The callback to run on the GUI thread.
            *args: Positional arguments handed to the callback.

        Returns:
            str: The scheduled callback's identifier.
        """

    def show_update_available(self, result: UpdateCheckResult) -> None:
        """
        Notifies the user that a newer release is available.

        Args:
            result (UpdateCheckResult): The check outcome, exposing the newer
                release's version and page URL.
        """

    def show_popup(self, title: str, message: str) -> None:
        """
        Shows the user a short message.

        Args:
            title (str): Title of the popup.
            message (str): The message to display.
        """


# UpdateCoordinator runs an update check off the GUI thread and turns its outcome
# into the right user-facing response. UpdateChecker deliberately does only the
# fetch, so every consumer would otherwise write this same threading and
# presentation plumbing itself.
class UpdateCoordinator:

    ###########################################################################
    ###                   UpdateCoordinator -> __init__()                   ###
    ###########################################################################
    def __init__(self, current_version: str, repo: str, display: UpdateDisplay):
        """
        Initializes the UpdateCoordinator with the values the check needs and the
        window that presents its outcome.

        Args:
            current_version (str): The running application's version, injected by
                the caller (typically from its own VERSION constant).
            repo (str): The GitHub repository in "owner/name" form whose latest
                release is compared against current_version.
            display (UpdateDisplay): The application window that schedules work on
                the GUI thread and presents the outcome to the user.
        """

        self.current_version = current_version
        self.repo = repo
        self.display = display

    ###########################################################################
    ###                     UpdateCoordinator -> start()                    ###
    ###########################################################################
    def start(self, manual: bool = False) -> None:
        """
        Spawns a daemon thread that checks for a newer release.

        Running on a background thread keeps the GUI from blocking while waiting on
        the GitHub API, and the daemon flag ensures a slow or stalled request can
        never delay application shutdown.

        Args:
            manual (bool): True when the check was triggered manually by the user
                (who should always get feedback), False for the silent startup
                check.
        """

        threading.Thread(target=self._run_check, args=(manual,), daemon=True).start()

    ###########################################################################
    ###                  UpdateCoordinator -> _run_check()                  ###
    ###########################################################################
    def _run_check(self, manual: bool = False) -> None:
        """
        Worker-thread body for an update check.

        Performs the (blocking, but silent-on-failure) update check off the GUI
        thread, then hands the result back to the GUI thread via display.after() so
        the toolkit is only ever touched from the thread that owns it.

        Args:
            manual (bool): Passed through to _handle_result so it knows whether to
                surface "up to date"/failure feedback.
        """

        result = UpdateChecker(
            current_version=self.current_version, repo=self.repo
        ).check_for_update()
        self.display.after(0, self._handle_result, result, manual)

    ###########################################################################
    ###                UpdateCoordinator -> _handle_result()                ###
    ###########################################################################
    def _handle_result(
        self, result: UpdateCheckResult | None, manual: bool = False
    ) -> None:
        """
        Handles the outcome of an update check on the GUI thread.

        Always shows the update popup when a strictly newer release exists. For a
        manual check the user also gets feedback when no update is available
        (an info popup) or the check failed (an error popup), so a deliberate
        action always confirms an outcome. The startup check (manual=False) stays
        silent in those cases so the user is never interrupted on launch.

        Args:
            result (UpdateCheckResult | None): The comparison outcome from
                UpdateChecker.check_for_update(), or None if the check failed.
            manual (bool): True when the check was triggered manually by the user,
                enabling the up-to-date/failure feedback.
        """

        if result and result.update_available:
            self.display.show_update_available(result)
        elif manual:
            if result is None:
                self.display.show_popup(
                    "Update Check Failed",
                    "Could not check for updates. Please check your internet "
                    "connection and try again.",
                )
            else:
                self.display.show_popup(
                    "No Updates Available",
                    f"You're running the latest version ({self.current_version}).",
                )
