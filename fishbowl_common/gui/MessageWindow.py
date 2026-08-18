import tkinter as tk

from fishbowl_common.gui.color_theme import Theme
from fishbowl_common.gui.ThemedSubwindow import ThemedSubwindow


# MessageWindow class for showing the user a short informational or error message.
# It replaces tkinter's native messagebox dialogs (which on Windows default to the
# center of the screen and ignore the application's styling) with a small themed
# window: a message label and a single OK button. Like the other themed subwindows
# it snapshots the active theme/font at open time and centers itself over the main
# application window (both handled by ThemedSubwindow).
class MessageWindow(ThemedSubwindow):

    ###########################################################################
    ###                     MessageWindow -> __init__()                    ###
    ###########################################################################
    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        message: str,
        theme: Theme,
        font_family: str,
        font_size: int,
    ):
        """
        Initializes the MessageWindow object

        Args:
            parent (tk.Misc): The parent window this window is attached to
            title (str): Title of the message window
            message (str): The message to display to the user
            theme (Theme): The color theme to style the window with, snapshotted
                at open time
            font_family (str): The font family to display the text with
            font_size (int): The font size to display the text with
        """

        super().__init__(parent, title, theme, font_family, font_size)

        # The message to display to the user
        self.message = message

        # Tkinter Widgets
        # fmt:off
        self.message_label: tk.Label  | None = None
        self.ok_button:     tk.Button | None = None
        # fmt:on

        self.build_widgets()

        # Position the window over the main application window rather than letting
        # it default to the top-left corner (or center) of the screen
        self._center_over_parent()

    ###########################################################################
    ###                   MessageWindow -> build_widgets()                 ###
    ###########################################################################
    def build_widgets(self):
        """
        Creates the label showing the message and the OK button used to dismiss
        the window
        """

        # Label showing the message. wraplength keeps long messages from forcing
        # an excessively wide window.
        self.message_label = tk.Label(
            self,
            text=self.message,
            wraplength=360,
            justify="center",
            font=(self.font_family, self.font_size, "bold"),
            bg=self.theme.bg_main,
            fg=self.theme.label_fg,
        )
        self.message_label.pack(padx=20, pady=(20, 10))

        # OK button to dismiss the window
        self.ok_button = tk.Button(
            self,
            text="OK",
            command=self.destroy,
            bg=self.theme.button_bg,
            fg=self.theme.button_fg,
            activebackground=self.theme.accent,
            activeforeground=self.theme.fg_text,
            relief="flat",
            font=(self.font_family, self.font_size, "bold"),
        )
        self.ok_button.pack(pady=(0, 20))
