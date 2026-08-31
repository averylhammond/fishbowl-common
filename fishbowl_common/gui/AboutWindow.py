import tkinter as tk

from fishbowl_common.gui.color_theme import Theme
from fishbowl_common.gui.ThemedSubwindow import ThemedSubwindow


# AboutWindow class to show the user which version of the application they are
# running. It is a small, read-only window displaying the application name and
# current version, with a single Close button. Both the name and the version are
# injected by the consuming application, so the window carries no knowledge of
# which app it belongs to. Like the other themed subwindows it snapshots the
# active theme/font at open time and centers itself over the main application
# window (both handled by ThemedSubwindow).
class AboutWindow(ThemedSubwindow):

    ###########################################################################
    ###                      AboutWindow -> __init__()                     ###
    ###########################################################################
    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        app_name: str,
        version: str,
        theme: Theme,
        font_family: str,
        font_size: int,
    ) -> None:
        """
        Initializes the AboutWindow object

        Args:
            parent: The parent window this window is attached to
            title: Title of the about window
            app_name: The application name to display
            version: The current application version to display
            theme: The color theme to style the window with, snapshotted at open time
            font_family: The font family to display the text with
            font_size: The font size to display the text with
        """

        super().__init__(parent, title, theme, font_family, font_size)

        # The application name and version to display to the user
        self.app_name = app_name
        self.version = version

        # Tkinter Widgets
        # fmt:off
        self.info_label:   tk.Label  | None = None
        self.close_button: tk.Button | None = None
        # fmt:on

        self.build_widgets()

        # Position the window over the main application window rather than letting
        # it default to the top-left corner of the screen
        self._center_over_parent()

    ###########################################################################
    ###                    AboutWindow -> build_widgets()                  ###
    ###########################################################################
    def build_widgets(self) -> None:
        """
        Creates the label showing the application name and current version, and
        the Close button used to dismiss the window
        """

        # Label showing the application name and current version
        self.info_label = tk.Label(
            self,
            text=f"{self.app_name}\nVersion {self.version}",
            font=(self.font_family, self.font_size, "bold"),
            bg=self.theme.bg_main,
            fg=self.theme.label_fg,
        )
        self.info_label.pack(padx=20, pady=(20, 10))

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
