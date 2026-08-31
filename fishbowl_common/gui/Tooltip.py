import tkinter as tk

from fishbowl_common.gui.color_theme import Theme


# Tooltip class to display informational text when the user hovers over a widget.
# Tkinter has no built-in tooltip, so this binds the target widget's hover events
# to show and hide a small borderless Toplevel positioned near the widget. The
# tooltip is styled with the active theme/font so it matches the rest of the UI.
class Tooltip:

    # Delay (in milliseconds) before a hovered tooltip appears, so it does not
    # flicker as the pointer merely passes over a widget on its way elsewhere.
    SHOW_DELAY_MS = 500

    ###########################################################################
    ###                       Tooltip -> __init__()                        ###
    ###########################################################################
    def __init__(
        self,
        widget: tk.Widget,
        text: str,
        theme: Theme,
        font_family: str,
        font_size: int,
    ) -> None:
        """
        Initializes the Tooltip object and binds it to the target widget's hover
        events.

        Args:
            widget: The widget that shows this tooltip when hovered
            text: The informational text to display on hover
            theme: The color theme to style the tooltip with
            font_family: The font family to display the text with
            font_size: The font size to display the text with
        """

        # The widget this tooltip is attached to
        self.widget = widget

        # The informational text shown on hover
        self.text = text

        # Styling applied to the tooltip popup; can be updated via update_style
        # so the tooltip follows live theme/font changes on the main window
        self.theme = theme
        self.font_family = font_family
        self.font_size = font_size

        # The popup window, created on hover-in and destroyed on hover-out
        self.tip_window: tk.Toplevel | None = None

        # The id of any pending scheduled show, kept so it can be cancelled if the
        # pointer leaves before the tooltip has appeared
        self.scheduled_id: str | None = None

        # Show on hover-in; hide on hover-out or when the widget is clicked.
        # add="+" so these do not clobber any other bindings on the widget.
        self.widget.bind("<Enter>", self._schedule_show, add="+")
        self.widget.bind("<Leave>", self._hide, add="+")
        self.widget.bind("<ButtonPress>", self._hide, add="+")

    ###########################################################################
    ###                    Tooltip -> _schedule_show()                     ###
    ###########################################################################
    def _schedule_show(self, _event: tk.Event | None = None) -> None:
        """
        Schedules the tooltip to appear after SHOW_DELAY_MS, cancelling any show
        already pending so a single hover never queues multiple popups.

        Args:
            _event: The tkinter event that triggered the hover (unused)
        """
        self._cancel_scheduled()
        self.scheduled_id = self.widget.after(self.SHOW_DELAY_MS, self._show)

    ###########################################################################
    ###                         Tooltip -> _show()                         ###
    ###########################################################################
    def _show(self) -> None:
        """
        Creates and displays the borderless tooltip popup just below the widget.
        Does nothing if the tooltip is already shown or has no text.
        """

        # Never stack popups, and never show an empty tooltip
        if self.tip_window or not self.text:
            return

        # Position the tooltip just below-right of the widget's top-left corner
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        # A borderless Toplevel that holds the tip label
        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.overrideredirect(True)
        self.tip_window.geometry(f"+{x}+{y}")

        # The label shows the tip text, styled with the active theme/font
        label = tk.Label(
            self.tip_window,
            text=self.text,
            bg=self.theme.bg_entry,
            fg=self.theme.fg_text,
            relief="solid",
            borderwidth=1,
            justify="left",
            font=(self.font_family, self.font_size),
            padx=6,
            pady=3,
        )
        label.pack()

    ###########################################################################
    ###                         Tooltip -> _hide()                         ###
    ###########################################################################
    def _hide(self, _event: tk.Event | None = None) -> None:
        """
        Hides the tooltip popup if shown and cancels any pending scheduled show.

        Args:
            _event: The tkinter event that triggered the hide (unused)
        """
        self._cancel_scheduled()
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

    ###########################################################################
    ###                    Tooltip -> _cancel_scheduled()                  ###
    ###########################################################################
    def _cancel_scheduled(self) -> None:
        """
        Cancels a pending scheduled show, if one exists, so it does not fire after
        the pointer has already left the widget.
        """
        if self.scheduled_id is not None:
            self.widget.after_cancel(self.scheduled_id)
            self.scheduled_id = None

    ###########################################################################
    ###                      Tooltip -> update_style()                     ###
    ###########################################################################
    def update_style(self, theme: Theme, font_family: str, font_size: int) -> None:
        """
        Updates the theme/font used for the tooltip so it stays consistent when
        the user changes the application's theme or font at runtime. If the
        tooltip is currently shown, it is hidden so it is rebuilt with the new
        styling on the next hover.

        Args:
            theme: The new color theme to style the tooltip with
            font_family: The new font family to display the text with
            font_size: The new font size to display the text with
        """
        self.theme = theme
        self.font_family = font_family
        self.font_size = font_size

        # Rebuild on next hover so the change is not shown half-applied
        if self.tip_window:
            self._hide()
