import tkinter as tk

from fishbowl_common.gui.color_theme import Theme


# ThemedSubwindow is the base class for a consuming application's transient
# secondary windows: MessageWindow, AboutWindow, FileEditorWindow and
# UpdateWindow here, plus any an application defines itself. It centralizes the
# setup every one of them shares: attaching to the parent window, snapshotting
# the active theme/font at open time so the window stays styled consistently
# with the rest of the application, setting the title and background, and
# centering the window over the parent. Subclasses build their own widgets and
# call _center_over_parent() once those widgets exist, so the window can be
# sized and positioned over the parent.
class ThemedSubwindow(tk.Toplevel):

    ###########################################################################
    ###                    ThemedSubwindow -> __init__()                    ###
    ###########################################################################
    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        theme: Theme,
        font_family: str,
        font_size: int,
    ) -> None:
        """
        Initializes the common state shared by every themed subwindow

        Args:
            parent (tk.Misc): The parent window this window is attached to and
                centered over
            title (str): Title shown in the window's title bar
            theme (Theme): The color theme to style the window with, snapshotted
                at open time
            font_family (str): The font family to display the text with
            font_size (int): The font size to display the text with
        """

        super().__init__(parent)

        # Snapshot the active theme/font at open time so the window is styled
        # consistently with the rest of the application
        self.theme = theme
        self.font_family = font_family
        self.font_size = font_size

        self.title(title)
        self.configure(bg=theme.bg_main)

    ###########################################################################
    ###               ThemedSubwindow -> _center_over_parent()             ###
    ###########################################################################
    def _center_over_parent(self) -> None:
        """
        Positions this window centered over its parent (the window it was opened
        from) so it appears near the application rather than in the top-left
        corner of the screen. Falls back to the default placement if the parent
        geometry is unavailable. Subclasses should call this once their widgets
        have been built, so the window's requested size is known.
        """

        parent = self.master
        if parent is None:
            return

        # Make sure this window's requested size has been computed before we use
        # it to center the window
        self.update_idletasks()

        # The parent's position (in screen coordinates) and size
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        # This window's requested size
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()

        # Top-left corner that centers this window over the parent
        x = parent_x + (parent_width - width) // 2
        y = parent_y + (parent_height - height) // 2

        self.geometry(f"+{x}+{y}")
