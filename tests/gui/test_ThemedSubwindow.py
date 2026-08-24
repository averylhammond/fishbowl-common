import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from fishbowl_common.gui.ThemedSubwindow import ThemedSubwindow
from fishbowl_common.gui.color_theme import DARK
from fishbowl_common.gui.font_settings import DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE


###############################################################################
###                    ThemedSubwindow -> Test Helpers                      ###
###############################################################################
def _build_subwindow():
    """
    Builds a ThemedSubwindow in complete isolation from tkinter: the real
    Toplevel.__init__ is neutralized and the inherited methods the constructor
    calls (title/configure) are mocked so no real window is created.

    Returns:
        types.SimpleNamespace: Holds the constructed window (`window`) and the
            mocked title/configure methods (`title`, `configure`).
    """

    with (
        patch.object(tk.Toplevel, "__init__", return_value=None),
        patch.object(ThemedSubwindow, "title") as mock_title,
        patch.object(ThemedSubwindow, "configure") as mock_configure,
    ):

        window = ThemedSubwindow(
            parent=MagicMock(),
            title="Test Window",
            theme=DARK,
            font_family=DEFAULT_FONT_FAMILY,
            font_size=DEFAULT_FONT_SIZE,
        )

    return SimpleNamespace(window=window, title=mock_title, configure=mock_configure)


###############################################################################
###                  Tests ThemedSubwindow -> __init__()                    ###
###############################################################################
def test_init_snapshots_theme_font_and_sets_title_and_background():
    """
    Verifies that the base constructor snapshots the active theme/font, sets the
    window title, and paints the window background with the theme color.
    """

    built = _build_subwindow()

    # The active theme/font are snapshotted onto the window
    assert built.window.theme is DARK
    assert built.window.font_family == DEFAULT_FONT_FAMILY
    assert built.window.font_size == DEFAULT_FONT_SIZE

    # The title bar text and themed background are applied
    built.title.assert_called_once_with("Test Window")
    built.configure.assert_called_once_with(bg=DARK.bg_main)


###############################################################################
###             Tests ThemedSubwindow -> _center_over_parent()              ###
###############################################################################
def test_center_over_parent_positions_window_over_parent():
    """
    Verifies that _center_over_parent positions the window so it is centered over
    its parent, using the parent's screen position and size and the window's own
    requested size.
    """

    window = _build_subwindow().window

    # Fake parent geometry: a 400x300 window at screen position (1000, 500)
    parent = MagicMock()
    parent.winfo_rootx.return_value = 1000
    parent.winfo_rooty.return_value = 500
    parent.winfo_width.return_value = 400
    parent.winfo_height.return_value = 300
    window.master = parent

    with (
        patch.object(ThemedSubwindow, "update_idletasks"),
        patch.object(ThemedSubwindow, "winfo_reqwidth", return_value=200),
        patch.object(ThemedSubwindow, "winfo_reqheight", return_value=100),
        patch.object(ThemedSubwindow, "geometry") as mock_geometry,
    ):
        window._center_over_parent()

    # x = 1000 + (400 - 200) // 2 = 1100 ; y = 500 + (300 - 100) // 2 = 600
    mock_geometry.assert_called_once_with("+1100+600")


def test_center_over_parent_no_parent_does_nothing():
    """
    Verifies that _center_over_parent leaves placement to Tk (does not call
    geometry) when the window has no parent to center over.
    """

    window = _build_subwindow().window
    window.master = None

    with patch.object(ThemedSubwindow, "geometry") as mock_geometry:
        window._center_over_parent()

    mock_geometry.assert_not_called()
