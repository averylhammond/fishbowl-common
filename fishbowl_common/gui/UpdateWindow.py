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


# UpdateWindow class to notify the user that a newer release is available. It is a
# small window showing the available version alongside an "Exit and Update" button
# that opens the release's GitHub page in the user's browser and then closes the
# application, plus a Close button to dismiss it without updating. Like the other
# themed subwindows it snapshots the active theme/font at open time and centers
# itself over the main application window (both handled by ThemedSubwindow).
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
    ):
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
        """

        super().__init__(parent, title, theme, font_family, font_size)

        # The newer release's version and the page to send the user to
        self.latest_version = latest_version
        self.release_url = release_url

        # Closes the application once the user has been sent to the download page
        self.close_app_callback = close_app_callback

        # Guards against repeated clicks stacking multiple close timers
        self._closing = False

        # Tkinter Widgets
        # fmt:off
        self.info_label:    tk.Label  | None = None
        self.update_button: tk.Button | None = None
        self.close_button:  tk.Button | None = None
        # fmt:on

        self.build_widgets()

        # Position the window over the main application window rather than letting
        # it default to the top-left corner of the screen
        self._center_over_parent()

    ###########################################################################
    ###                   UpdateWindow -> build_widgets()                  ###
    ###########################################################################
    def build_widgets(self):
        """
        Creates the label announcing the available version, the "Exit and Update"
        button that opens the release page and closes the app, and the Close button
        used to dismiss the window without updating
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
    ###                 UpdateWindow -> _open_release_page()               ###
    ###########################################################################
    def _open_release_page(self):
        """
        Opens the release's GitHub page in the user's default browser so they can
        download the newer version, then closes the application after a short delay.

        The app must exit so the downloaded installer can overwrite the running
        executable, which Windows keeps file-locked while the process is alive;
        leaving it open is what makes the installer hang trying to close it. The
        delay (CLOSE_DELAY_MS) lets the browser surface before the app disappears.
        Repeated clicks are ignored once a close has been scheduled.
        """

        if self._closing:
            return
        self._closing = True

        webbrowser.open(self.release_url)

        # Tell the user what is about to happen and prevent further interaction
        # with a window that is on its way out
        if self.info_label is not None:
            self.info_label.config(text="Closing to install update…")
        if self.update_button is not None:
            self.update_button.config(state=tk.DISABLED)

        # Close the whole application (not just this window) once the user has been
        # sent to the download page, so the installer can replace the running exe
        self.after(CLOSE_DELAY_MS, self.close_app_callback)
