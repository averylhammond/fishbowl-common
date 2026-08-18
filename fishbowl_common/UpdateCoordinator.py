import threading
from functools import partial
from typing import Callable, Protocol

from fishbowl_common.UpdateChecker import UpdateChecker, UpdateCheckResult
from fishbowl_common.UpdateDownloader import UpdateDownloader
from fishbowl_common.UpdateInstaller import UpdateInstaller

# Reported to a caller's progress callback as (bytes received, bytes expected), and
# to its completion callback as whether the installer actually started.
ProgressCallback = Callable[[int, int], None]
FinishedCallback = Callable[[bool], None]

# Handed to the display when the update can be installed in place: calling it with
# a progress and a completion callback starts the download.
StartInstall = Callable[[ProgressCallback, FinishedCallback], None]


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

    def show_update_available(
        self, result: UpdateCheckResult, start_install: StartInstall | None = None
    ) -> None:
        """
        Notifies the user that a newer release is available.

        Args:
            result (UpdateCheckResult): The check outcome, exposing the newer
                release's version and page URL.
            start_install (StartInstall | None): Starts the download-and-install
                flow, or None when this release cannot be installed in place and
                the user must be sent to the release page instead.
        """

    def show_popup(self, title: str, message: str) -> None:
        """
        Shows the user a short message.

        Args:
            title (str): Title of the popup.
            message (str): The message to display.
        """


# UpdateCoordinator runs an update check off the GUI thread and turns its outcome
# into the right user-facing response, then - when the release publishes an
# installer this platform can run - downloads and starts that installer, again off
# the GUI thread. UpdateChecker, UpdateDownloader and UpdateInstaller each do one
# step and none of them know about threads or windows; this is where those steps
# are sequenced and marshalled back onto the thread that owns the toolkit.
class UpdateCoordinator:

    ###########################################################################
    ###                   UpdateCoordinator -> __init__()                   ###
    ###########################################################################
    def __init__(
        self,
        current_version: str,
        repo: str,
        display: UpdateDisplay,
        asset_pattern: str | None = None,
    ):
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
            asset_pattern (str | None): An fnmatch pattern naming the release's
                installer, e.g. "FishbowlInvoiceTool_Setup.exe". Injected because
                each application names its installer differently; when omitted, the
                user is offered only the manual download flow.
        """

        self.current_version = current_version
        self.repo = repo
        self.display = display
        self.asset_pattern = asset_pattern

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
            current_version=self.current_version,
            repo=self.repo,
            asset_pattern=self.asset_pattern,
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

        Always shows the update popup when a strictly newer release exists, handing
        it the install callback when the release can be installed in place. For a
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
            start_install = (
                partial(self.start_install, result)
                if self._can_install(result)
                else None
            )
            self.display.show_update_available(result, start_install)
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

    ###########################################################################
    ###                 UpdateCoordinator -> _can_install()                 ###
    ###########################################################################
    def _can_install(self, result: UpdateCheckResult) -> bool:
        """
        Reports whether this release can be downloaded and installed in place.

        Both assets are required: the installer is what runs, and the checksums
        file is what proves the installer is the one the release published. Without
        either - or on a platform this installer is not built for - the user is
        offered the manual download instead.

        Args:
            result (UpdateCheckResult): The outcome of the update check.

        Returns:
            bool: True if the in-place install can be offered.
        """

        return bool(
            result.installer_asset
            and result.checksums_asset
            and UpdateInstaller.is_supported()
        )

    ###########################################################################
    ###                 UpdateCoordinator -> start_install()                ###
    ###########################################################################
    def start_install(
        self,
        result: UpdateCheckResult,
        on_progress: ProgressCallback,
        on_finished: FinishedCallback,
    ) -> None:
        """
        Spawns a daemon thread that downloads the release's installer and starts it.

        Args:
            result (UpdateCheckResult): The outcome of the update check, carrying
                the installer and checksums assets to fetch.
            on_progress (ProgressCallback): Called on the GUI thread with the bytes
                received so far and the total expected.
            on_finished (FinishedCallback): Called on the GUI thread with True once
                the installer has been started, or False if any step failed.
        """

        threading.Thread(
            target=self._run_install,
            args=(result, on_progress, on_finished),
            daemon=True,
        ).start()

    ###########################################################################
    ###                 UpdateCoordinator -> _run_install()                 ###
    ###########################################################################
    def _run_install(
        self,
        result: UpdateCheckResult,
        on_progress: ProgressCallback,
        on_finished: FinishedCallback,
    ) -> None:
        """
        Worker-thread body for the download-and-install flow.

        Fetches the published digest, downloads the installer against it, and only
        then starts it. Every failure along the way arrives at the same place - a
        False handed to on_finished - so the window needs one fallback path rather
        than one per step. Progress and the outcome both cross back to the GUI
        thread through display.after().

        Args:
            result (UpdateCheckResult): The outcome of the update check, carrying
                the installer and checksums assets to fetch.
            on_progress (ProgressCallback): Called on the GUI thread with the bytes
                received so far and the total expected.
            on_finished (FinishedCallback): Called on the GUI thread with whether
                the installer was started.
        """

        downloader = UpdateDownloader()
        installer_asset = result.installer_asset

        expected_sha256 = downloader.fetch_expected_sha256(
            result.checksums_asset.download_url, installer_asset.name
        )

        installer = None
        if expected_sha256:
            installer = downloader.download(
                installer_asset.download_url,
                downloader.default_destination(installer_asset.name),
                expected_sha256,
                installer_asset.size,
                lambda received, total: self.display.after(
                    0, on_progress, received, total
                ),
            )

        started = installer is not None and UpdateInstaller().launch(
            installer, installer.with_name(f"{installer.stem}_install.log")
        )

        self.display.after(0, on_finished, started)
