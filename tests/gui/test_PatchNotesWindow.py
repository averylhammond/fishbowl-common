import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from fishbowl_common.gui.PatchNotesWindow import PatchNotesWindow
from fishbowl_common.gui.color_theme import DARK
from fishbowl_common.gui.font_settings import DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE


###############################################################################
###                    PatchNotesWindow -> Test Helpers                     ###
###############################################################################
def _distinct_widget(*_args, **_kwargs):
    """
    Side effect for patched tkinter widget classes that returns a fresh
    MagicMock for every constructed widget, so each widget attribute on the
    window (e.g. heading_label vs. text_box) is a distinct mock that can be
    asserted on independently.
    """

    return MagicMock()


def _build_window(app_name="Test App", version="1.0", notes="- Added a thing"):
    """
    Builds a PatchNotesWindow in complete isolation from tkinter: the real
    Toplevel.__init__ is neutralized, the inherited methods the constructor calls
    (title/configure) are mocked, and every widget class is replaced so no real
    window or widgets are created.

    Args:
        app_name (str): The application name to build the window with
        version (str): The version whose notes are being announced
        notes (str): The notes text to build the window with

    Returns:
        types.SimpleNamespace: Holds the constructed window (`window`) and the
            patched tk.Label/tk.Button/ScrolledText classes (`label_cls`,
            `button_cls`, `text_cls`) so tests can assert on how each widget was
            constructed.
    """

    with (
        patch.object(tk.Toplevel, "__init__", return_value=None),
        patch.object(PatchNotesWindow, "title"),
        patch.object(PatchNotesWindow, "configure"),
        patch.object(PatchNotesWindow, "_center_over_parent"),
        patch(
            "fishbowl_common.gui.PatchNotesWindow.tk.Label",
            side_effect=_distinct_widget,
        ) as label_cls,
        patch(
            "fishbowl_common.gui.PatchNotesWindow.tk.Button",
            side_effect=_distinct_widget,
        ) as button_cls,
        patch(
            "fishbowl_common.gui.PatchNotesWindow.scrolledtext.ScrolledText",
            side_effect=_distinct_widget,
        ) as text_cls,
    ):

        window = PatchNotesWindow(
            parent=MagicMock(),
            title="What's New",
            app_name=app_name,
            version=version,
            notes=notes,
            theme=DARK,
            font_family=DEFAULT_FONT_FAMILY,
            font_size=DEFAULT_FONT_SIZE,
        )

    return SimpleNamespace(
        window=window,
        label_cls=label_cls,
        button_cls=button_cls,
        text_cls=text_cls,
    )


###############################################################################
###               Tests PatchNotesWindow -> build_widgets()                 ###
###############################################################################
def test_build_widgets_creates_heading_text_box_and_close_button():
    """
    Verifies that build_widgets constructs the heading, the notes box and the
    Close button, storing all three on the window.
    """

    built = _build_window()

    assert built.window.heading_label is not None
    assert built.window.text_box is not None
    assert built.window.close_button is not None


def test_heading_names_the_injected_app_name_and_version():
    """
    Verifies that the heading names the application and the version being
    announced, both of which are injected, so the window carries no app-specific
    text of its own and reads correctly from either consuming application.
    """

    built = _build_window(app_name="Fishbowl Widget Tool", version="9.9.9")

    assert (
        built.label_cls.call_args.kwargs["text"]
        == "What's new in Fishbowl Widget Tool 9.9.9"
    )


def test_notes_are_inserted_into_the_text_box():
    """
    Verifies that the notes passed in are written into the text box, since they
    arrive as a string rather than being read from a file by the window.
    """

    built = _build_window(notes="- Fixed the second thing")

    built.window.text_box.insert.assert_called_once_with(
        tk.END, "- Fixed the second thing"
    )


def test_text_box_is_disabled_after_the_notes_are_inserted():
    """
    Verifies that the notes box is made read-only once the notes are in it.
    There is nothing here for a user to edit, and an editable box only invites
    them to try.
    """

    built = _build_window()

    built.window.text_box.configure.assert_called_once_with(state="disabled")


def test_widgets_use_theme_and_font():
    """
    Verifies that the heading, notes box and Close button are styled with the
    snapshotted theme colors and font, matching the rest of the application. The
    notes box uses the display font rather than a fixed-width one, because the
    notes are prose rather than aligned columns.
    """

    # The heading uses the theme background, label foreground, and bold font
    built = _build_window()
    label_kwargs = built.label_cls.call_args.kwargs
    assert label_kwargs["bg"] == DARK.bg_main
    assert label_kwargs["fg"] == DARK.label_fg
    assert label_kwargs["font"] == (DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, "bold")

    # The notes box uses the theme entry colors and the application's font
    text_kwargs = built.text_cls.call_args.kwargs
    assert text_kwargs["bg"] == DARK.bg_entry
    assert text_kwargs["fg"] == DARK.fg_text
    assert text_kwargs["font"] == (DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE)

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
