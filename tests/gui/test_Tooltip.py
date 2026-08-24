import pytest
from unittest.mock import patch, MagicMock

from fishbowl_common.gui.Tooltip import Tooltip
from fishbowl_common.gui.color_theme import DARK, LIGHT
from fishbowl_common.gui.font_settings import DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE


###############################################################################
###                        Tooltip -> Test Fixture                          ###
###############################################################################
@pytest.fixture
def tooltip():
    """
    Builds a Tooltip attached to a mock widget. Tooltip.__init__ only binds hover
    events on the widget (no real tkinter windows are created until a hover), so a
    plain MagicMock widget is sufficient and keeps the unit isolated.

    Returns:
        Tooltip: A Tooltip bound to a MagicMock widget, styled with the DARK theme
            and the default font.
    """

    widget = MagicMock()
    widget.winfo_rootx.return_value = 100
    widget.winfo_rooty.return_value = 200
    widget.winfo_height.return_value = 30

    return Tooltip(
        widget=widget,
        text="Helpful hint",
        theme=DARK,
        font_family=DEFAULT_FONT_FAMILY,
        font_size=DEFAULT_FONT_SIZE,
    )


###############################################################################
###                       Tests Tooltip -> __init__()                       ###
###############################################################################
def test_init_binds_hover_events(tooltip):
    """
    Verifies that __init__ binds the show/hide handlers to the widget's hover and
    click events without overriding existing bindings.

    Args:
        tooltip (pytest.fixture): Provides a Tooltip bound to a mock widget
    """

    bound_events = [call.args[0] for call in tooltip.widget.bind.call_args_list]
    assert "<Enter>" in bound_events
    assert "<Leave>" in bound_events
    assert "<ButtonPress>" in bound_events

    # Bindings are added (add="+") so they do not clobber other handlers
    for call in tooltip.widget.bind.call_args_list:
        assert call.kwargs.get("add") == "+"


###############################################################################
###                    Tests Tooltip -> _schedule_show()                    ###
###############################################################################
def test_schedule_show_schedules_after_delay(tooltip):
    """
    Verifies that _schedule_show queues the popup to appear after the show delay
    and records the scheduled id so it can be cancelled later.

    Args:
        tooltip (pytest.fixture): Provides a Tooltip bound to a mock widget
    """

    tooltip.widget.after.return_value = "after#1"

    tooltip._schedule_show()

    tooltip.widget.after.assert_called_once_with(Tooltip.SHOW_DELAY_MS, tooltip._show)
    assert tooltip.scheduled_id == "after#1"


def test_schedule_show_cancels_existing_schedule(tooltip):
    """
    Verifies that scheduling a show cancels any already-pending show so a single
    hover never queues multiple popups.

    Args:
        tooltip (pytest.fixture): Provides a Tooltip bound to a mock widget
    """

    tooltip.scheduled_id = "stale"

    tooltip._schedule_show()

    tooltip.widget.after_cancel.assert_called_once_with("stale")


###############################################################################
###                        Tests Tooltip -> _show()                         ###
###############################################################################
@patch("fishbowl_common.gui.Tooltip.tk.Label")
@patch("fishbowl_common.gui.Tooltip.tk.Toplevel")
def test_show_creates_positioned_popup(mock_toplevel, mock_label, tooltip):
    """
    Verifies that _show creates a borderless popup near the widget and fills it
    with a label containing the tip text.

    Args:
        mock_toplevel (unittest.mock.MagicMock): Mocks tk.Toplevel
        mock_label (unittest.mock.MagicMock): Mocks tk.Label
        tooltip (pytest.fixture): Provides a Tooltip bound to a mock widget
    """

    tooltip._show()

    # A borderless, positioned popup is created and tracked
    mock_toplevel.assert_called_once_with(tooltip.widget)
    mock_toplevel.return_value.overrideredirect.assert_called_once_with(True)
    mock_toplevel.return_value.geometry.assert_called_once_with("+120+235")
    assert tooltip.tip_window is mock_toplevel.return_value

    # The label shows the tip text and is packed into the popup
    assert mock_label.call_args.kwargs["text"] == "Helpful hint"
    mock_label.return_value.pack.assert_called_once()


@patch("fishbowl_common.gui.Tooltip.tk.Toplevel")
def test_show_does_nothing_when_already_shown(mock_toplevel, tooltip):
    """
    Verifies that _show does not create a second popup when one is already shown.

    Args:
        mock_toplevel (unittest.mock.MagicMock): Mocks tk.Toplevel
        tooltip (pytest.fixture): Provides a Tooltip bound to a mock widget
    """

    tooltip.tip_window = MagicMock()

    tooltip._show()

    mock_toplevel.assert_not_called()


@patch("fishbowl_common.gui.Tooltip.tk.Toplevel")
def test_show_does_nothing_without_text(mock_toplevel, tooltip):
    """
    Verifies that _show does not create a popup when there is no tip text.

    Args:
        mock_toplevel (unittest.mock.MagicMock): Mocks tk.Toplevel
        tooltip (pytest.fixture): Provides a Tooltip bound to a mock widget
    """

    tooltip.text = ""

    tooltip._show()

    mock_toplevel.assert_not_called()


###############################################################################
###                        Tests Tooltip -> _hide()                         ###
###############################################################################
def test_hide_destroys_popup_and_cancels_schedule(tooltip):
    """
    Verifies that _hide tears down the popup and cancels any pending scheduled
    show.

    Args:
        tooltip (pytest.fixture): Provides a Tooltip bound to a mock widget
    """

    popup = MagicMock()
    tooltip.tip_window = popup
    tooltip.scheduled_id = "after#1"

    tooltip._hide()

    popup.destroy.assert_called_once_with()
    assert tooltip.tip_window is None
    tooltip.widget.after_cancel.assert_called_once_with("after#1")


###############################################################################
###                     Tests Tooltip -> update_style()                     ###
###############################################################################
def test_update_style_updates_attributes_and_rebuilds_when_shown(tooltip):
    """
    Verifies that update_style stores the new theme/font and hides a currently
    shown popup so it is rebuilt with the new styling on the next hover.

    Args:
        tooltip (pytest.fixture): Provides a Tooltip bound to a mock widget
    """

    popup = MagicMock()
    tooltip.tip_window = popup

    tooltip.update_style(LIGHT, "Arial", 18)

    # The new styling is stored
    assert tooltip.theme == LIGHT
    assert tooltip.font_family == "Arial"
    assert tooltip.font_size == 18

    # The shown popup is torn down so it rebuilds with the new style next hover
    popup.destroy.assert_called_once_with()
    assert tooltip.tip_window is None


def test_update_style_does_not_rebuild_when_hidden(tooltip):
    """
    Verifies that update_style only stores the new styling (no teardown) when no
    popup is currently shown.

    Args:
        tooltip (pytest.fixture): Provides a Tooltip bound to a mock widget
    """

    tooltip.tip_window = None

    tooltip.update_style(LIGHT, "Arial", 18)

    assert tooltip.theme == LIGHT
    assert tooltip.tip_window is None
