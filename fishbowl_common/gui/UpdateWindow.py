import tkinter as tk
import webbrowser
from typing import Callable

from fishbowl_common.gui.color_theme import Theme
from fishbowl_common.gui.ThemedSubwindow import ThemedSubwindow


# Delay, in milliseconds, between opening the release page and closing the
# application. The app must exit so the Windows installer can replace the running
# executable (a locked .exe cannot be overwritten); the brief delay lets the
# browser come to the foreground before the app disappears.
CLOSE_DELAY_MS = 3000

# Delay, in milliseconds, between the installer starting and the application
# closing. Much shorter than CLOSE_DELAY_MS because nothing has to surface first:
# it only needs to be long enough for the window to paint its final message, and
# the installer is already waiting on this process to release its executable.
INSTALL_CLOSE_DELAY_MS = 500

# Size, in pixels, of the download progress bar. It is drawn on a Canvas rather
# than being a ttk.Progressbar so it can be colored from the snapshotted theme like
# every other widget in this package.
PROGRESS_BAR_WIDTH = 260
PROGRESS_BAR_HEIGHT = 14


# UpdateWindow class to notify the user that a newer release is available. It is a
# small window showing the available version alongside the ways to get it: when the
# release publishes an installer this platform can run, an "Update and Restart"
# button that downloads it, shows its progress, starts it and closes the app; and
# always an "Exit and Update" button that opens the release's GitHub page for a
# manual download, plus a Close button to dismiss the window without updating. The
# manual route is also where a failed automatic update lands, so a broken download
# never leaves the user worse off than before. Like the other themed subwindows it
# snapshots the active theme/font at open time and centers itself over the main
# application window (both handled by ThemedSubwindow).
class UpdateWindow(ThemedSubwindow):

    ###########################################################################
    ###                     UpdateWindow -> __init__()                     ###
    ###########################################################################
    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        latest_version: str,
        release_url: str,
        close_app_callback: Callable[[], None],
        theme: Theme,
        font_family: str,
        font_size: int,
        start_install_callback: (
            Callable[[Callable[[int, int], None], Callable[[bool], None]], None] | None
        ) = None,
    ) -> None:
        """
        Initializes the UpdateWindow object

        Args:
            parent (tk.Misc): The parent window this window is attached to
            title (str): Title of the update window
            latest_version (str): The newer release's version to display
            release_url (str): The URL of the release's page on GitHub, opened when
                the "Exit and Update" button is pressed
            close_app_callback (Callable[[], None]): Closes the whole application,
                invoked a few seconds after "Exit and Update" is pressed so the
                installer can replace the running executable
            theme (Theme): The color theme to style the window with, snapshotted
                at open time
            font_family (str): The font family to display the text with
            font_size (int): The font size to display the text with
            start_install_callback (Callable | None): Starts the download-and-install
                flow, taking the progress callback (bytes received, bytes expected)
                and the completion callback (whether the installer started). None
                when this release cannot be installed in place, which is what leaves
                the window offering only the manual download
        """

        super().__init__(parent, title, theme, font_family, font_size)

        # The newer release's version and the page to send the user to
        self.latest_version = latest_version
        self.release_url = release_url

        # Closes the application once the user has been sent to the download page
        self.close_app_callback = close_app_callback

        # Downloads and starts the installer, or None when only the manual download
        # can be offered
        self.start_install_callback = start_install_callback

        # Guards against repeated clicks stacking multiple close timers
        self._closing = False

        # Tkinter Widgets
        # fmt:off
        self.info_label:     tk.Label  | None = None
        self.install_button: tk.Button | None = None
        self.update_button:  tk.Button | None = None
        self.close_button:   tk.Button | None = None
        self.progress_bar:   tk.Canvas | None = None
        # fmt:on

        self.build_widgets()

        # Position the window over the main application window rather than letting
        # it default to the top-left corner of the screen
        self._center_over_parent()

    ###########################################################################
    ###                   UpdateWindow -> build_widgets()                  ###
    ###########################################################################
    def build_widgets(self) -> None:
        """
        Creates the label announcing the available version, the "Update and Restart"
        button and its progress bar (only when the release can be installed in
        place), the "Exit and Update" button that opens the release page and closes
        the app, and the Close button used to dismiss the window without updating
        """

        # Label announcing that a newer release is available
        self.info_label = tk.Label(
            self,
            text=f"Version {self.latest_version} is available",
            font=(self.font_family, self.font_size, "bold"),
            bg=self.theme.bg_main,
            fg=self.theme.label_fg,
        )
        self.info_label.pack(padx=20, pady=(20, 10))

        # "Update and Restart" button and the bar tracking its download, built only
        # when there is an installer to run. The bar is left unpacked until the
        # download starts, so the window opens at its resting size
        if self.start_install_callback is not None:
            self.progress_bar = tk.Canvas(
                self,
                width=PROGRESS_BAR_WIDTH,
                height=PROGRESS_BAR_HEIGHT,
                bg=self.theme.bg_entry,
                highlightthickness=0,
            )

            self.install_button = tk.Button(
                self,
                text="Update and Restart",
                command=self._update_and_restart,
                bg=self.theme.button_bg,
                fg=self.theme.button_fg,
                activebackground=self.theme.accent,
                activeforeground=self.theme.fg_text,
                relief="flat",
                font=(self.font_family, self.font_size, "bold"),
            )
            self.install_button.pack(pady=(0, 10))

        # "Exit and Update" button to open the release page in the user's browser
        # and then close the application so the installer can replace the exe
        self.update_button = tk.Button(
            self,
            text="Exit and Update",
            command=self._open_release_page,
            bg=self.theme.button_bg,
            fg=self.theme.button_fg,
            activebackground=self.theme.accent,
            activeforeground=self.theme.fg_text,
            relief="flat",
            font=(self.font_family, self.font_size, "bold"),
        )
        self.update_button.pack(pady=(0, 10))

        # Close button to dismiss the window
        self.close_button = tk.Button(
            self,
            text="Close",
            command=self.destroy,
            bg=self.theme.button_bg,
            fg=self.theme.button_fg,
            activebackground=self.theme.accent,
            activeforeground=self.theme.fg_text,
            relief="flat",
            font=(self.font_family, self.font_size, "bold"),
        )
        self.close_button.pack(pady=(0, 20))

    ###########################################################################
    ###                 UpdateWindow -> _update_and_restart()              ###
    ###########################################################################
    def _update_and_restart(self) -> None:
        """
        Downloads the release's installer, showing its progress, and hands the
        outcome to _on_install_finished().

        The download itself runs elsewhere, off the GUI thread; this only starts it
        and reports on it. Repeated clicks are ignored once one is underway, and
        both buttons are disabled so the manual route cannot be taken out from
        under a download that is already running.
        """

        if self._closing:
            return
        self._closing = True

        self._disable_buttons()

        # Show an empty bar immediately rather than an unchanged window, since the
        # first progress report only arrives once the connection is open
        if self.progress_bar is not None:
            self.progress_bar.pack(padx=20, pady=(0, 10), before=self.install_button)
        self._on_progress(0, 0)

        self.start_install_callback(self._on_progress, self._on_install_finished)

    ###########################################################################
    ###                    UpdateWindow -> _on_progress()                  ###
    ###########################################################################
    def _on_progress(self, received: int, total: int) -> None:
        """
        Redraws the progress bar as the download advances.

        Args:
            received (int): Bytes downloaded so far
            total (int): Bytes expected in total, or 0 when the size is not known
                (in which case the bar stays empty and only the label speaks)
        """

        fraction = min(1.0, received / total) if total else 0.0

        if self.progress_bar is not None:
            self.progress_bar.delete("all")
            self.progress_bar.create_rectangle(
                0,
                0,
                int(PROGRESS_BAR_WIDTH * fraction),
                PROGRESS_BAR_HEIGHT,
                fill=self.theme.accent,
                width=0,
            )

        if self.info_label is not None:
            self.info_label.config(
                text=f"Downloading update… {int(fraction * 100)}%"
            )

    ###########################################################################
    ###                UpdateWindow -> _on_install_finished()              ###
    ###########################################################################
    def _on_install_finished(self, started: bool) -> None:
        """
        Handles the end of the download-and-install flow.

        On success the application has to get out of the installer's way, since it
        cannot replace an executable this process still holds open. On failure -
        a download that broke off, a digest that did not match, an installer that
        would not start - the user is sent to the release page instead, so a failed
        automatic update costs them nothing but the wait.

        Args:
            started (bool): Whether the installer was successfully started
        """

        if started:
            if self.info_label is not None:
                self.info_label.config(text="Installing update…")
            self.after(INSTALL_CLOSE_DELAY_MS, self.close_app_callback)
        else:
            self._send_to_release_page(
                "Automatic update failed. Opening the release page…"
            )

    ###########################################################################
    ###                 UpdateWindow -> _open_release_page()               ###
    ###########################################################################
    def _open_release_page(self) -> None:
        """
        Opens the release's GitHub page in the user's default browser so they can
        download the newer version, then closes the application after a short delay.

        Repeated clicks are ignored once a close has been scheduled.
        """

        if self._closing:
            return
        self._closing = True

        self._send_to_release_page()

    ###########################################################################
    ###               UpdateWindow -> _send_to_release_page()              ###
    ###########################################################################
    def _send_to_release_page(
        self, message: str = "Closing to install update…"
    ) -> None:
        """
        Sends the user to the release page and closes the application after a short
        delay.

        The app must exit so the downloaded installer can overwrite the running
        executable, which Windows keeps file-locked while the process is alive;
        leaving it open is what makes the installer hang trying to close it. The
        delay (CLOSE_DELAY_MS) lets the browser surface before the app disappears.

        This is deliberately not guarded by _closing: it is the fallback a failed
        automatic update lands on, and by then _closing is already set.

        Args:
            message (str): What to tell the user is happening
        """

        webbrowser.open(self.release_url)

        # Tell the user what is about to happen and prevent further interaction
        # with a window that is on its way out
        if self.info_label is not None:
            self.info_label.config(text=message)
        self._disable_buttons()

        # Close the whole application (not just this window) once the user has been
        # sent to the download page, so the installer can replace the running exe
        self.after(CLOSE_DELAY_MS, self.close_app_callback)

    ###########################################################################
    ###                  UpdateWindow -> _disable_buttons()                ###
    ###########################################################################
    def _disable_buttons(self) -> None:
        """
        Disables both update buttons, so neither route can be started while the
        other is already underway
        """

        for button in (self.install_button, self.update_button):
            if button is not None:
                button.config(state=tk.DISABLED)
