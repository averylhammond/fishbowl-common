# This file contains color definitions and theme definitions for the application.
from dataclasses import dataclass

# Blues
BLUE = "#3498db"
LIGHT_BLUE = "#5dade2"
DARK_BLUE = "#2980b9"
SKY_BLUE = "#87ceeb"
NAVY = "#001f3f"
DEEP_NAVY = "#1a3a5c"
TEAL = "#1abc9c"
CYAN = "#00bcd4"
AQUA = "#00ffff"
TURQUOISE = "#40e0d0"

# Greens
GREEN = "#2ecc71"
LIGHT_GREEN = "#58d68d"
DARK_GREEN = "#27ae60"
OLIVE = "#808000"
LIME = "#cddc39"
FOREST_GREEN = "#228b22"
DARK_FOREST_GREEN = "#1a2e1a"
MEDIUM_FOREST_GREEN = "#2d4a2d"
MINT = "#98ff98"

# Yellows
YELLOW = "#f1c40f"
LIGHT_YELLOW = "#fff9c4"
GOLD = "#ffd700"
AMBER = "#ffbf00"

# Oranges
ORANGE = "#e67e22"
LIGHT_ORANGE = "#ffb347"
DARK_ORANGE = "#ff8c00"
PEACH = "#ffdab9"

# Reds
RED = "#e74c3c"
LIGHT_RED = "#ff6f61"
DARK_RED = "#c0392b"
MAROON = "#800000"
CRIMSON = "#dc143c"

# Pinks
PINK = "#ff69b4"
LIGHT_PINK = "#ffb6c1"
HOT_PINK = "#ff1493"
MAGENTA = "#ff00ff"

# Purples
PURPLE = "#9b59b6"
LIGHT_PURPLE = "#d7bde2"
DARK_PURPLE = "#6c3483"
VIOLET = "#8f00ff"
INDIGO = "#4b0082"

# Browns
BROWN = "#a0522d"
TAN = "#d2b48c"
BEIGE = "#f5f5dc"

# Whites/Greys/Blacks
IVORY = "#fffff0"
WHITE = "#ffffff"
LIGHT_GRAY = "#f5f5f5"
SILVER = "#c0c0c0"
GRAY = "#808080"
MEDIUM_GRAY = "#36393f"
DARK_GRAY = "#2c2f33"
DARKER_GRAY = "#23272a"
CHARCOAL = "#36454f"
BLACK = "#000000"


# Use a dataclass since there is no need for anything else
@dataclass
class Theme:
    name: str
    bg_main: str
    bg_entry: str
    fg_text: str
    accent: str
    button_bg: str
    button_fg: str
    label_fg: str


# Define color themes for use by the application
DARK = Theme(
    name="Dark",
    bg_main=DARK_GRAY,
    bg_entry=MEDIUM_GRAY,
    fg_text=IVORY,
    accent=LIGHT_BLUE,
    button_bg=BLUE,
    button_fg=IVORY,
    label_fg=BLUE,
)

LIGHT = Theme(
    name="Light",
    bg_main=LIGHT_GRAY,
    bg_entry=WHITE,
    fg_text=DARK_GRAY,
    accent=DARK_BLUE,
    button_bg=BLUE,
    button_fg=WHITE,
    label_fg=DARK_BLUE,
)

OCEAN = Theme(
    name="Ocean",
    bg_main=NAVY,
    bg_entry=DEEP_NAVY,
    fg_text=IVORY,
    accent=CYAN,
    button_bg=TEAL,
    button_fg=NAVY,
    label_fg=CYAN,
)

FOREST = Theme(
    name="Forest",
    bg_main=DARK_FOREST_GREEN,
    bg_entry=MEDIUM_FOREST_GREEN,
    fg_text=IVORY,
    accent=LIGHT_GREEN,
    button_bg=DARK_GREEN,
    button_fg=IVORY,
    label_fg=GREEN,
)

# Provide a list of all themes that are available for use
ALL_THEMES = [DARK, LIGHT, OCEAN, FOREST]

# Map each theme's name to its Theme so a persisted theme name can be resolved
# back to a Theme on startup. Built from ALL_THEMES so new themes are included
# automatically without touching the lookup.
THEME_BY_NAME = {theme.name: theme for theme in ALL_THEMES}
