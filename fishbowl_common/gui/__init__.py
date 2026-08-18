# The GUI half of the package: the themed tkinter windows and styling data the
# Fishbowl desktop tools share. It is imported separately from the top-level
# package (which stays tkinter-free) so a consumer running headless never loads
# tkinter; see the [gui] extra in pyproject.toml.

# Only RED is re-exported from the color palette: it is the one bare color a
# consumer styles a widget with directly (the Exit button). The rest of the
# palette is reachable from fishbowl_common.gui.color_theme.
from fishbowl_common.gui.color_theme import (
    Theme,
    RED,
    DARK,
    LIGHT,
    OCEAN,
    FOREST,
    ALL_THEMES,
    THEME_BY_NAME,
)
from fishbowl_common.gui.font_settings import (
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    FONT_FAMILIES,
    FONT_SIZES,
    MONOSPACE_FONT_FAMILY,
)
from fishbowl_common.gui.ThemedSubwindow import ThemedSubwindow
from fishbowl_common.gui.MessageWindow import MessageWindow
from fishbowl_common.gui.AboutWindow import AboutWindow
from fishbowl_common.gui.FileEditorWindow import FileEditorWindow
from fishbowl_common.gui.UpdateWindow import UpdateWindow
from fishbowl_common.gui.Tooltip import Tooltip

__all__ = [
    "Theme",
    "RED",
    "DARK",
    "LIGHT",
    "OCEAN",
    "FOREST",
    "ALL_THEMES",
    "THEME_BY_NAME",
    "DEFAULT_FONT_FAMILY",
    "DEFAULT_FONT_SIZE",
    "FONT_FAMILIES",
    "FONT_SIZES",
    "MONOSPACE_FONT_FAMILY",
    "ThemedSubwindow",
    "MessageWindow",
    "AboutWindow",
    "FileEditorWindow",
    "UpdateWindow",
    "Tooltip",
]
