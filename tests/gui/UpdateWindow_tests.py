import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from fishbowl_common.gui.UpdateWindow import UpdateWindow, CLOSE_DELAY_MS
from fishbowl_common.gui.color_theme import DARK
from fishbowl_common.gui.font_settings import DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE


###############################################################################
###                      UpdateWindow -> Test Helpers                      ###
###############################################################################
def _distinct_widget(*_args, **_kwargs):
    """
    Side effect for patched tkinter widget classes that returns a fresh
    MagicMock for every constructed widget, so each widget attribute on the
    window (e.g. info_label vs. update_button vs. close_button) is a distinct
    mock that can be asserted on independently.
    """

    return MagicMock()


def _build_window(
    latest_version="9.9.9",
    release_url="https://example.com/release",
    close_app_callback=None,
):
    """
    Builds an UpdateWindow in complete isolation from tkinter: the real
    Toplevel.__init__ is neutralized, the inherited methods the constructor calls
    (title/configure) are mocked, and every widget class is replaced so no real
    window or widgets are created.

    Args:
        latest_version (str): The available version to build the window with
        release_url (str): The release URL to build the window with
        close_app_callback (Callable | None): The app-close callback to build the
            window with; a fresh MagicMock is used when not supplied

    Returns:
        types.SimpleNamespace: Holds the constructed window (`window`), the patched
            tk.Label/tk.Button classes (`label_cls`, `button_cls`), and the
            close-app callback (`close_app_callback`) so tests can assert on how
            each widget was constructed and that the app is closed.
    """

    close_app_callback = close_app_callback or MagicMock()

    with (
        patch.object(tk.Toplevel, "__init__", return_value=None),
        patch.object(UpdateWindow, "title"),
        patch.object(UpdateWindow, "configure"),
        patch.object(UpdateWindow, "_center_over_parent"),
        patch(
            "fishbowl_common.gui.UpdateWindow.tk.Label", side_effect=_distinct_widget
        ) as label_cls,
        patch(
            "fishbowl_common.gui.UpdateWindow.tk.Button", side_effect=_distinct_widget
        ) as button_cls,
    ):

        window = UpdateWindow(
            parent=MagicMock(),
            title="Update Available",
            latest_version=latest_version,
            release_url=release_url,
            close_app_callback=close_app_callback,
            theme=DARK,
            font_family=DEFAULT_FONT_FAMILY,
            font_size=DEFAULT_FONT_SIZE,
        )

    return SimpleNamespace(
        window=window,
        label_cls=label_cls,
        button_cls=button_cls,
        close_app_callback=close_app_callback,
    )


###############################################################################
###                 Tests UpdateWindow -> build_widgets()                  ###
###############################################################################
def test_build_widgets_creates_label_and_buttons():
    """
    Verifies that build_widgets constructs the info label, the "Exit and Update"
    button, and the Close button, storing each on the window.
    """

    built = _build_window()

    assert built.window.info_label is not None
    assert built.window.update_button is not None
    assert built.window.close_button is not None


def test_info_label_shows_available_version():
    """
    Verifies that the info label announces the available version that was passed
    in, so the user sees which newer version is available.
    """

    built = _build_window(latest_version="9.9.9")

    label_call = built.label_cls.call_args
    assert label_call.kwargs["text"] == "Version 9.9.9 is available"


def test_label_and_buttons_use_theme_and_font():
    """
    Verifies that the label and both buttons are styled with the snapshotted theme
    colors and font, matching the rest of the application.
    """

    built = _build_window()

    # The label uses the theme background, label foreground, and bold font
    label_kwargs = built.label_cls.call_args.kwargs
    assert label_kwargs["bg"] == DARK.bg_main
    assert label_kwargs["fg"] == DARK.label_fg
    assert label_kwargs["font"] == (DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, "bold")

    # Both buttons use the theme button colors and bold font
    for button_call in built.button_cls.call_args_list:
        assert button_call.kwargs["bg"] == DARK.button_bg
        assert button_call.kwargs["fg"] == DARK.button_fg
        assert button_call.kwargs["font"] == (
            DEFAULT_FONT_FAMILY,
            DEFAULT_FONT_SIZE,
            "bold",
        )


def test_close_button_is_wired_to_destroy():
    """
    Verifies that the Close button's command is the window's destroy method, so
    pressing it dismisses the window.
    """

    built = _build_window()

    # The Close button is the second button constructed (after "Exit and Update")
    close_kwargs = built.button_cls.call_args_list[1].kwargs
    assert close_kwargs["text"] == "Close"
    assert close_kwargs["command"] == built.window.destroy


def test_update_button_is_wired_to_open_release_page():
    """
    Verifies that the "Exit and Update" button's command opens the release page, so
    pressing it sends the user to the release on GitHub.
    """

    built = _build_window()

    # The "Exit and Update" button is the first button constructed
    update_kwargs = built.button_cls.call_args_list[0].kwargs
    assert update_kwargs["text"] == "Exit and Update"
    assert update_kwargs["command"] == built.window._open_release_page


###############################################################################
###               Tests UpdateWindow -> _open_release_page()               ###
###############################################################################
def test_open_release_page_opens_url_in_browser():
    """
    Verifies that _open_release_page opens the release URL in the user's browser.
    """

    built = _build_window(release_url="https://example.com/release")
    # after() would otherwise hit the real Tcl interpreter, which the isolated
    # window has none of; the scheduling itself is asserted in a dedicated test
    built.window.after = MagicMock()

    with patch("fishbowl_common.gui.UpdateWindow.webbrowser.open") as mock_open:
        built.window._open_release_page()

    mock_open.assert_called_once_with("https://example.com/release")


def test_open_release_page_schedules_app_close_after_delay():
    """
    Verifies that _open_release_page schedules the application to close after the
    configured delay, so the installer can replace the running executable.
    """

    built = _build_window()
    built.window.after = MagicMock()

    with patch("fishbowl_common.gui.UpdateWindow.webbrowser.open"):
        built.window._open_release_page()

    built.window.after.assert_called_once_with(
        CLOSE_DELAY_MS, built.close_app_callback
    )


def test_open_release_page_ignores_repeat_clicks():
    """
    Verifies that clicking "Exit and Update" again after a close has been scheduled
    does not open a second browser tab or stack a second close timer.
    """

    built = _build_window()
    built.window.after = MagicMock()

    with patch("fishbowl_common.gui.UpdateWindow.webbrowser.open") as mock_open:
        built.window._open_release_page()
        built.window._open_release_page()

    # The browser is opened and the close scheduled exactly once despite two clicks
    mock_open.assert_called_once()
    built.window.after.assert_called_once()


def test_open_release_page_disables_button_and_updates_label():
    """
    Verifies that _open_release_page tells the user the app is closing and disables
    the "Exit and Update" button so an outgoing window cannot be re-triggered.
    """

    built = _build_window()
    built.window.after = MagicMock()

    with patch("fishbowl_common.gui.UpdateWindow.webbrowser.open"):
        built.window._open_release_page()

    built.window.info_label.config.assert_called_once_with(
        text="Closing to install update…"
    )
    built.window.update_button.config.assert_called_once_with(state=tk.DISABLED)
