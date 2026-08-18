import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from fishbowl_common.gui.MessageWindow import MessageWindow
from fishbowl_common.gui.color_theme import DARK
from fishbowl_common.gui.font_settings import DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE


###############################################################################
###                      MessageWindow -> Test Helpers                     ###
###############################################################################
def _distinct_widget(*_args, **_kwargs):
    """
    Side effect for patched tkinter widget classes that returns a fresh
    MagicMock for every constructed widget, so each widget attribute on the
    window (e.g. message_label vs. ok_button) is a distinct mock that can be
    asserted on independently.
    """

    return MagicMock()


def _build_window(message="Something happened"):
    """
    Builds a MessageWindow in complete isolation from tkinter: the real
    Toplevel.__init__ is neutralized, the inherited methods the constructor calls
    (title/configure) are mocked, and every widget class is replaced so no real
    window or widgets are created.

    Args:
        message (str): The message to build the window with

    Returns:
        types.SimpleNamespace: Holds the constructed window (`window`) and the
            patched tk.Label/tk.Button classes (`label_cls`, `button_cls`) so
            tests can assert on how each widget was constructed.
    """

    with (
        patch.object(tk.Toplevel, "__init__", return_value=None),
        patch.object(MessageWindow, "title"),
        patch.object(MessageWindow, "configure"),
        patch.object(MessageWindow, "_center_over_parent"),
        patch(
            "fishbowl_common.gui.MessageWindow.tk.Label", side_effect=_distinct_widget
        ) as label_cls,
        patch(
            "fishbowl_common.gui.MessageWindow.tk.Button", side_effect=_distinct_widget
        ) as button_cls,
    ):

        window = MessageWindow(
            parent=MagicMock(),
            title="Notice",
            message=message,
            theme=DARK,
            font_family=DEFAULT_FONT_FAMILY,
            font_size=DEFAULT_FONT_SIZE,
        )

    return SimpleNamespace(window=window, label_cls=label_cls, button_cls=button_cls)


###############################################################################
###                 Tests MessageWindow -> build_widgets()                 ###
###############################################################################
def test_build_widgets_creates_label_and_ok_button():
    """
    Verifies that build_widgets constructs the message label and the OK button,
    storing both on the window.
    """

    built = _build_window()

    assert built.window.message_label is not None
    assert built.window.ok_button is not None


def test_message_label_shows_message():
    """
    Verifies that the message label displays the message that was passed in.
    """

    built = _build_window(message="Custom message text")

    assert built.label_cls.call_args.kwargs["text"] == "Custom message text"


def test_label_and_button_use_theme_and_font():
    """
    Verifies that the label and OK button are styled with the snapshotted theme
    colors and font, matching the rest of the application.
    """

    built = _build_window()

    # The label uses the theme background, label foreground, and bold font
    label_kwargs = built.label_cls.call_args.kwargs
    assert label_kwargs["bg"] == DARK.bg_main
    assert label_kwargs["fg"] == DARK.label_fg
    assert label_kwargs["font"] == (DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, "bold")

    # The OK button uses the theme button colors and bold font
    button_kwargs = built.button_cls.call_args.kwargs
    assert button_kwargs["bg"] == DARK.button_bg
    assert button_kwargs["fg"] == DARK.button_fg
    assert button_kwargs["font"] == (DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, "bold")


def test_ok_button_is_wired_to_destroy():
    """
    Verifies that the OK button's command is the window's destroy method, so
    pressing it dismisses the window.
    """

    built = _build_window()

    assert built.button_cls.call_args.kwargs["text"] == "OK"
    assert built.button_cls.call_args.kwargs["command"] == built.window.destroy
