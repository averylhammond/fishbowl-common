import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from fishbowl_common.gui.UpdateWindow import (
    UpdateWindow,
    CLOSE_DELAY_MS,
    INSTALL_CLOSE_DELAY_MS,
    PROGRESS_BAR_HEIGHT,
    PROGRESS_BAR_WIDTH,
)
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
    start_install_callback=None,
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
        start_install_callback (Callable | None): The install callback to build the
            window with; None (the default) builds the window a release with no
            installable asset would get, offering only the manual download

    Returns:
        types.SimpleNamespace: Holds the constructed window (`window`), the patched
            tk.Label/tk.Button/tk.Canvas classes (`label_cls`, `button_cls`,
            `canvas_cls`), and both injected callbacks (`close_app_callback`,
            `start_install_callback`) so tests can assert on how each widget was
            constructed and on what the window does with them.
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
        patch(
            "fishbowl_common.gui.UpdateWindow.tk.Canvas", side_effect=_distinct_widget
        ) as canvas_cls,
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
            start_install_callback=start_install_callback,
        )

    return SimpleNamespace(
        window=window,
        label_cls=label_cls,
        button_cls=button_cls,
        canvas_cls=canvas_cls,
        close_app_callback=close_app_callback,
        start_install_callback=start_install_callback,
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


###############################################################################
###             Tests UpdateWindow -> the in-place install offer            ###
###############################################################################
def test_build_widgets_omits_the_install_offer_without_an_install_callback():
    """
    Verifies that a release with nothing installable in place builds the window as
    it has always been - the manual download and nothing else - with neither the
    "Update and Restart" button nor its progress bar created.
    """

    built = _build_window()

    assert built.window.install_button is None
    assert built.window.progress_bar is None
    built.canvas_cls.assert_not_called()
    assert len(built.button_cls.call_args_list) == 2


def test_build_widgets_creates_the_install_button_when_an_install_is_offered():
    """
    Verifies that a release that can be installed in place gets the "Update and
    Restart" button, wired to the install flow and offered above the manual route.
    """

    built = _build_window(start_install_callback=MagicMock())

    assert built.window.install_button is not None

    # The install button is built first, so it reads above "Exit and Update"
    install_kwargs = built.button_cls.call_args_list[0].kwargs
    assert install_kwargs["text"] == "Update and Restart"
    assert install_kwargs["command"] == built.window._update_and_restart
    assert built.button_cls.call_args_list[1].kwargs["text"] == "Exit and Update"


def test_progress_bar_is_themed_and_left_unpacked_until_a_download_starts():
    """
    Verifies that the progress bar is styled from the snapshotted theme like every
    other widget here, and is built but not laid out, so the window opens at its
    resting size rather than showing an empty bar the user has not asked for.
    """

    built = _build_window(start_install_callback=MagicMock())

    canvas_kwargs = built.canvas_cls.call_args.kwargs
    assert canvas_kwargs["bg"] == DARK.bg_entry
    assert canvas_kwargs["width"] == PROGRESS_BAR_WIDTH
    assert canvas_kwargs["height"] == PROGRESS_BAR_HEIGHT
    built.window.progress_bar.pack.assert_not_called()


###############################################################################
###               Tests UpdateWindow -> _update_and_restart()               ###
###############################################################################
def test_update_and_restart_starts_the_install_with_its_own_callbacks():
    """
    Verifies that pressing "Update and Restart" hands the injected callback the two
    methods it reports back through, so the download itself runs elsewhere - off the
    GUI thread - and this window only presents it.
    """

    start_install = MagicMock()
    built = _build_window(start_install_callback=start_install)

    built.window._update_and_restart()

    start_install.assert_called_once_with(
        built.window._on_progress, built.window._on_install_finished
    )


def test_update_and_restart_shows_the_bar_and_disables_both_buttons():
    """
    Verifies that starting a download lays out the progress bar and disables both
    update routes, so the manual one cannot be taken out from under a download that
    is already running.
    """

    built = _build_window(start_install_callback=MagicMock())

    built.window._update_and_restart()

    built.window.progress_bar.pack.assert_called_once()
    built.window.install_button.config.assert_called_once_with(state=tk.DISABLED)
    built.window.update_button.config.assert_called_once_with(state=tk.DISABLED)


def test_update_and_restart_ignores_repeat_clicks():
    """
    Verifies that clicking "Update and Restart" again while a download is underway
    does not start a second one.
    """

    start_install = MagicMock()
    built = _build_window(start_install_callback=start_install)

    built.window._update_and_restart()
    built.window._update_and_restart()

    start_install.assert_called_once()


def test_update_and_restart_blocks_the_manual_route_once_it_is_underway():
    """
    Verifies that the browser flow cannot be started while a download is running,
    since that path closes the application - and would take the download with it.
    """

    built = _build_window(start_install_callback=MagicMock())
    built.window.after = MagicMock()

    built.window._update_and_restart()
    with patch("fishbowl_common.gui.UpdateWindow.webbrowser.open") as mock_open:
        built.window._open_release_page()

    mock_open.assert_not_called()


###############################################################################
###                  Tests UpdateWindow -> _on_progress()                   ###
###############################################################################
def test_on_progress_fills_the_bar_and_reports_the_percentage():
    """
    Verifies that a progress report redraws the bar to the fraction received and
    says so in words, so the user can see a large download advancing.
    """

    built = _build_window(start_install_callback=MagicMock())

    built.window._on_progress(512, 2048)

    built.window.progress_bar.delete.assert_called_with("all")
    rectangle_args = built.window.progress_bar.create_rectangle.call_args.args
    assert rectangle_args == (
        0,
        0,
        int(PROGRESS_BAR_WIDTH * 0.25),
        PROGRESS_BAR_HEIGHT,
    )
    built.window.info_label.config.assert_called_with(text="Downloading update… 25%")


def test_on_progress_leaves_the_bar_empty_when_the_size_is_unknown():
    """
    Verifies that a total of 0 - a transfer whose length neither the response nor
    the release declared - draws an empty bar rather than dividing by zero.
    """

    built = _build_window(start_install_callback=MagicMock())

    built.window._on_progress(1024, 0)

    rectangle_args = built.window.progress_bar.create_rectangle.call_args.args
    assert rectangle_args == (0, 0, 0, PROGRESS_BAR_HEIGHT)
    built.window.info_label.config.assert_called_with(text="Downloading update… 0%")


def test_on_progress_clamps_a_transfer_that_overruns_its_declared_size():
    """
    Verifies that receiving more than was declared fills the bar exactly rather than
    drawing past its end.
    """

    built = _build_window(start_install_callback=MagicMock())

    built.window._on_progress(4096, 2048)

    rectangle_args = built.window.progress_bar.create_rectangle.call_args.args
    assert rectangle_args == (0, 0, PROGRESS_BAR_WIDTH, PROGRESS_BAR_HEIGHT)
    built.window.info_label.config.assert_called_with(text="Downloading update… 100%")


###############################################################################
###              Tests UpdateWindow -> _on_install_finished()               ###
###############################################################################
def test_on_install_finished_closes_the_application_once_the_installer_starts():
    """
    Verifies that a started installer closes the whole application after a short
    delay: it cannot replace an executable this process still holds open.
    """

    built = _build_window(start_install_callback=MagicMock())
    built.window.after = MagicMock()

    built.window._on_install_finished(True)

    built.window.info_label.config.assert_called_with(text="Installing update…")
    built.window.after.assert_called_once_with(
        INSTALL_CLOSE_DELAY_MS, built.close_app_callback
    )


def test_on_install_finished_falls_back_to_the_release_page_on_failure():
    """
    Verifies that a failed automatic update sends the user to the release page
    instead, so a broken download costs them the wait and nothing more.
    """

    built = _build_window(
        release_url="https://example.com/release", start_install_callback=MagicMock()
    )
    built.window.after = MagicMock()

    with patch("fishbowl_common.gui.UpdateWindow.webbrowser.open") as mock_open:
        built.window._on_install_finished(False)

    mock_open.assert_called_once_with("https://example.com/release")
    built.window.info_label.config.assert_called_with(
        text="Automatic update failed. Opening the release page…"
    )
    built.window.after.assert_called_once_with(CLOSE_DELAY_MS, built.close_app_callback)


def test_a_failed_download_still_reaches_the_release_page_after_a_real_click():
    """
    Verifies that the fallback works from the state a real failure happens in -
    after "Update and Restart" was pressed, with the repeat-click guard already set.
    A fallback the guard blocked would leave the user with a dead window.
    """

    built = _build_window(start_install_callback=MagicMock())
    built.window.after = MagicMock()

    built.window._update_and_restart()
    with patch("fishbowl_common.gui.UpdateWindow.webbrowser.open") as mock_open:
        built.window._on_install_finished(False)

    mock_open.assert_called_once()
    built.window.after.assert_called_once_with(CLOSE_DELAY_MS, built.close_app_callback)
