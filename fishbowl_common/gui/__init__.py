# The GUI half of the package: the themed tkinter windows and styling data the
# Fishbowl desktop tools share. It is imported separately from the top-level
# package (which stays tkinter-free) so a consumer running headless never loads
# tkinter; see the [gui] extra in pyproject.toml.

from fishbowl_common.gui.about_window import AboutWindow
from fishbowl_common.gui.color_theme import (
    ALL_THEMES,
    DARK,
    FOREST,
    LIGHT,
    OCEAN,
    # The one bare color re-exported from the palette: it is the only one a consumer
    # styles a widget with directly (the Exit button). The rest of the palette stays
    # reachable from fishbowl_common.gui.color_theme.
    RED,
    THEME_BY_NAME,
    Theme,
)
from fishbowl_common.gui.file_editor_window import FileEditorWindow
from fishbowl_common.gui.font_settings import (
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    FONT_FAMILIES,
    FONT_SIZES,
    MONOSPACE_FONT_FAMILY,
)
from fishbowl_common.gui.message_window import MessageWindow
from fishbowl_common.gui.patch_notes_window import PatchNotesWindow
from fishbowl_common.gui.themed_subwindow import ThemedSubwindow
from fishbowl_common.gui.tooltip import Tooltip
from fishbowl_common.gui.update_window import UpdateWindow

__all__ = [
    "ALL_THEMES",
    "DARK",
    "DEFAULT_FONT_FAMILY",
    "DEFAULT_FONT_SIZE",
    "FONT_FAMILIES",
    "FONT_SIZES",
    "FOREST",
    "LIGHT",
    "MONOSPACE_FONT_FAMILY",
    "OCEAN",
    "RED",
    "THEME_BY_NAME",
    "AboutWindow",
    "FileEditorWindow",
    "MessageWindow",
    "PatchNotesWindow",
    "Theme",
    "ThemedSubwindow",
    "Tooltip",
    "UpdateWindow",
]
