import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from fishbowl_common.gui.AboutWindow import AboutWindow
from fishbowl_common.gui.color_theme import DARK
from fishbowl_common.gui.font_settings import DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE


###############################################################################
###                      AboutWindow -> Test Helpers                       ###
###############################################################################
def _distinct_widget(*_args, **_kwargs):
    """
    Side effect for patched tkinter widget classes that returns a fresh
    MagicMock for every constructed widget, so each widget attribute on the
    window (e.g. info_label vs. close_button) is a distinct mock that can be
    asserted on independently.
    """

    return MagicMock()


def _build_window(app_name="Test App", version="1.0"):
    """
    Builds an AboutWindow in complete isolation from tkinter: the real
    Toplevel.__init__ is neutralized, the inherited methods the constructor calls
    (title/configure) are mocked, and every widget class is replaced so no real
    window or widgets are created.

    Args:
        app_name (str): The application name to build the window with
        version (str): The version string to build the window with

    Returns:
        types.SimpleNamespace: Holds the constructed window (`window`) and the
            patched tk.Label/tk.Button classes (`label_cls`, `button_cls`) so
            tests can assert on how each widget was constructed.
    """

    with (
        patch.object(tk.Toplevel, "__init__", return_value=None),
        patch.object(AboutWindow, "title"),
        patch.object(AboutWindow, "configure"),
        patch.object(AboutWindow, "_center_over_parent"),
        patch(
            "fishbowl_common.gui.AboutWindow.tk.Label", side_effect=_distinct_widget
        ) as label_cls,
        patch(
            "fishbowl_common.gui.AboutWindow.tk.Button", side_effect=_distinct_widget
        ) as button_cls,
    ):

        window = AboutWindow(
            parent=MagicMock(),
            title="About",
            app_name=app_name,
            version=version,
            theme=DARK,
            font_family=DEFAULT_FONT_FAMILY,
            font_size=DEFAULT_FONT_SIZE,
        )

    return SimpleNamespace(window=window, label_cls=label_cls, button_cls=button_cls)


###############################################################################
###                  Tests AboutWindow -> build_widgets()                  ###
###############################################################################
def test_build_widgets_creates_label_and_close_button():
    """
    Verifies that build_widgets constructs the info label and the Close button,
    storing both on the window.
    """

    built = _build_window()

    assert built.window.info_label is not None
    assert built.window.close_button is not None


def test_info_label_shows_injected_app_name_and_version():
    """
    Verifies that the info label displays the application name and the version
    that were passed in, so the user sees which application and version they are
    running. Both are injected, so the window carries no app-specific text of its
    own and reads correctly from either consuming application.
    """

    built = _build_window(app_name="Fishbowl Widget Tool", version="9.9.9")

    label_call = built.label_cls.call_args
    assert label_call.kwargs["text"] == "Fishbowl Widget Tool\nVersion 9.9.9"


def test_label_and_button_use_theme_and_font():
    """
    Verifies that the label and Close button are styled with the snapshotted
    theme colors and font, matching the rest of the application.
    """

    built = _build_window()

    # The label uses the theme background, label foreground, and bold font
    label_kwargs = built.label_cls.call_args.kwargs
    assert label_kwargs["bg"] == DARK.bg_main
    assert label_kwargs["fg"] == DARK.label_fg
    assert label_kwargs["font"] == (DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, "bold")

    # The Close button uses the theme button colors and bold font
    button_kwargs = built.button_cls.call_args.kwargs
    assert button_kwargs["bg"] == DARK.button_bg
    assert button_kwargs["fg"] == DARK.button_fg
    assert button_kwargs["font"] == (DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, "bold")


def test_close_button_is_wired_to_destroy():
    """
    Verifies that the Close button's command is the window's destroy method, so
    pressing it dismisses the window.
    """

    built = _build_window()

    assert built.button_cls.call_args.kwargs["text"] == "Close"
    assert built.button_cls.call_args.kwargs["command"] == built.window.destroy
