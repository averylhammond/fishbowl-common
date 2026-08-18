import tkinter as tk
from tkinter import scrolledtext
from pathlib import Path
from typing import Callable

from fishbowl_common.gui.color_theme import Theme
from fishbowl_common.gui.font_settings import MONOSPACE_FONT_FAMILY
from fishbowl_common.gui.ThemedSubwindow import ThemedSubwindow


# FileEditorWindow class to view or edit a single text file natively within the
# application. The same window serves both editable files (with a Save button)
# and read-only ones (no Save button, editing disabled) via the editable flag.
# Theme/font snapshotting and centering over the parent are handled by
# ThemedSubwindow.
class FileEditorWindow(ThemedSubwindow):

    ###########################################################################
    ###                   FileEditorWindow -> __init__()                    ###
    ###########################################################################
    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        file_path: Path,
        initial_text: str,
        theme: Theme,
        font_family: str,
        font_size: int,
        editable: bool = True,
        save_callback: Callable[[Path, str], None] | None = None,
        text_width: int | None = None,
        text_height: int | None = None,
    ):
        """
        Initializes the FileEditorWindow object

        Args:
            parent (tk.Misc): The parent window this window is attached to
            title (str): Title of the editor window
            file_path (Path): The file path this window is viewing/editing, passed
                back to the save_callback when the user saves
            initial_text (str): The current file contents to display
            theme (Theme): The color theme to style the window with, snapshotted at
                open time
            font_family (str): The font family to display the text with
            font_size (int): The font size to display the text with
            editable (bool): Whether the contents can be edited and saved. When
                False, the text is read-only and no Save button is shown
                (used for viewing log files). Defaults to True
            save_callback (Callable[[Path, str], None] | None): Called with the
                file path and the edited contents when the user saves. Required
                when editable is True; ignored when editable is False
            text_width (int | None): Width of the text box in character cells.
                When None, tkinter's default width is used (suitable for short
                files). A caller with a longer one can request a wider box for
                easier reading
            text_height (int | None): Height of the text box in character cells.
                When None, tkinter's default height is used
        """

        super().__init__(parent, title, theme, font_family, font_size)

        # File this window is bound to; passed back to the save callback on save
        self.file_path = file_path

        # Whether the contents can be edited and saved
        self.editable = editable

        # Callback used to persist edits when the user saves
        self.save_callback = save_callback

        # Text box dimensions in character cells; None uses tkinter's defaults
        self.text_width = text_width
        self.text_height = text_height

        # Tkinter Widgets
        # fmt:off
        self.text_box:     scrolledtext.ScrolledText | None = None
        self.button_frame: tk.Frame                  | None = None
        self.save_button:  tk.Button                 | None = None
        self.close_button: tk.Button                 | None = None
        # fmt:on

        self.build_widgets(initial_text)

        # Position the window over the main application window rather than letting
        # it default to the top-left corner of the screen
        self._center_over_parent()

    ###########################################################################
    ###                 FileEditorWindow -> build_widgets()                 ###
    ###########################################################################
    def build_widgets(self, initial_text: str):
        """
        Creates the text box and action buttons (Save when editable, plus Close)
        for the window

        Args:
            initial_text (str): The current file contents to display in the text box
        """

        # Text box displaying the file contents. A fixed-width font is used (rather
        # than the application's display font) so columns in the underlying text
        # stay aligned, the way they appear in a text editor.
        # Only pass width/height when supplied so tkinter's defaults are kept for
        # short files; a caller with a longer one can request a bigger box
        size_kwargs = {}
        if self.text_width is not None:
            size_kwargs["width"] = self.text_width
        if self.text_height is not None:
            size_kwargs["height"] = self.text_height

        self.text_box = scrolledtext.ScrolledText(
            self,
            wrap="word",
            font=(MONOSPACE_FONT_FAMILY, self.font_size, "bold"),
            bg=self.theme.bg_entry,
            fg=self.theme.fg_text,
            insertbackground=self.theme.fg_text,
            relief="flat",
            **size_kwargs,
        )
        self.text_box.insert(tk.END, initial_text)
        self.text_box.pack(padx=20, pady=(20, 10), fill="both", expand=True)

        # Frame holding the action buttons along the bottom of the window
        self.button_frame = tk.Frame(self, bg=self.theme.bg_main)
        self.button_frame.pack(pady=(0, 20))

        # When editable, offer a Save button that persists the edits. When not
        # editable (log viewing), disable editing and show no Save button (the
        # Close button then sits where the Save button would have been).
        if self.editable:
            self.save_button = tk.Button(
                self.button_frame,
                text="Save",
                command=self.handle_save,
                bg=self.theme.button_bg,
                fg=self.theme.button_fg,
                activebackground=self.theme.accent,
                activeforeground=self.theme.fg_text,
                relief="flat",
                font=(self.font_family, self.font_size, "bold"),
            )
            self.save_button.grid(row=0, column=0, padx=10)
        else:
            self.text_box.configure(state="disabled")

        # Close button to dismiss the window; placed next to Save when present,
        # otherwise in the first column where Save would have been
        self.close_button = tk.Button(
            self.button_frame,
            text="Close",
            command=self.destroy,
            bg=self.theme.button_bg,
            fg=self.theme.button_fg,
            activebackground=self.theme.accent,
            activeforeground=self.theme.fg_text,
            relief="flat",
            font=(self.font_family, self.font_size, "bold"),
        )
        self.close_button.grid(row=0, column=1 if self.editable else 0, padx=10)

    ###########################################################################
    ###                  FileEditorWindow -> handle_save()                  ###
    ###########################################################################
    def handle_save(self):
        """
        Reads the current contents of the text box and forwards them, along with
        the bound file path, to the save_callback so the file is persisted
        """

        # Grab everything in the text box (tkinter appends a trailing newline that
        # is stripped so repeated saves do not accumulate blank lines)
        contents = self.text_box.get("1.0", tk.END)
        if contents.endswith("\n"):
            contents = contents[:-1]

        if self.save_callback:
            self.save_callback(self.file_path, contents)
