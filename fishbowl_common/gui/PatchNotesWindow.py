import tkinter as tk
from tkinter import scrolledtext

from fishbowl_common.gui.color_theme import Theme
from fishbowl_common.gui.ThemedSubwindow import ThemedSubwindow

# Size of the notes box, in character cells. Patch notes run longer than the
# handful of lines an AboutWindow shows, so the box is sized rather than left at
# tkinter's default.
TEXT_WIDTH = 64
TEXT_HEIGHT = 20


# PatchNotesWindow class to show the user what changed in the version they are
# now running, typically on the first launch after an update. It shows a heading
# naming the application and the version being announced, the notes themselves in
# a read-only scrolling box, and a single Close button. The notes arrive as a
# string rather than a file path, because they are frequently the concatenated
# sections of several releases (a user who skipped a version) and so are not a
# file on disk at all -- which, along with the heading and the prose font, is why
# this is its own window rather than a read-only FileEditorWindow. Both the
# application name and the version are injected, so the window carries no
# knowledge of which app it belongs to. Like the other themed subwindows it
# snapshots the active theme/font at open time and centers itself over the main
# application window (both handled by ThemedSubwindow).
class PatchNotesWindow(ThemedSubwindow):

    ###########################################################################
    ###                    PatchNotesWindow -> __init__()                   ###
    ###########################################################################
    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        app_name: str,
        version: str,
        notes: str,
        theme: Theme,
        font_family: str,
        font_size: int,
    ) -> None:
        """
        Initializes the PatchNotesWindow object

        Args:
            parent: The parent window this window is attached to
            title: Title of the patch notes window
            app_name: The application name to display in the heading
            version: The version whose notes are being announced
            notes: The notes to display, already selected by the caller
            theme: The color theme to style the window with, snapshotted at open time
            font_family: The font family to display the text with
            font_size: The font size to display the text with
        """

        super().__init__(parent, title, theme, font_family, font_size)

        # The application name and version named in the heading
        self.app_name = app_name
        self.version = version

        # Tkinter Widgets
        # fmt:off
        self.heading_label: tk.Label                    | None = None
        self.text_box:      scrolledtext.ScrolledText   | None = None
        self.close_button:  tk.Button                   | None = None
        # fmt:on

        self.build_widgets(notes)

        # Position the window over the main application window rather than letting
        # it default to the top-left corner of the screen
        self._center_over_parent()

    ###########################################################################
    ###                 PatchNotesWindow -> build_widgets()                 ###
    ###########################################################################
    def build_widgets(self, notes: str) -> None:
        """
        Creates the heading, the read-only notes box and the Close button used to
        dismiss the window

        Args:
            notes: The notes to display in the text box
        """

        # Heading naming the application and the version being announced
        self.heading_label = tk.Label(
            self,
            text=f"What's new in {self.app_name} {self.version}",
            font=(self.font_family, self.font_size, "bold"),
            bg=self.theme.bg_main,
            fg=self.theme.label_fg,
        )
        self.heading_label.pack(padx=20, pady=(20, 10))

        # Box holding the notes. The application's display font is used rather
        # than a fixed-width one because these are prose, not aligned columns.
        self.text_box = scrolledtext.ScrolledText(
            self,
            wrap="word",
            width=TEXT_WIDTH,
            height=TEXT_HEIGHT,
            font=(self.font_family, self.font_size),
            bg=self.theme.bg_entry,
            fg=self.theme.fg_text,
            relief="flat",
        )
        self.text_box.insert(tk.END, notes)

        # Disable the box once the notes are in it: there is nothing for the user
        # to edit here, and an editable box only invites them to try
        self.text_box.configure(state="disabled")
        self.text_box.pack(padx=20, pady=(0, 10), fill="both", expand=True)

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
