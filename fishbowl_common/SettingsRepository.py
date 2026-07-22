import sqlite3
from pathlib import Path
from typing import Callable


# SettingsRepository class to persist user-controlled settings (theme, font, etc.)
# in a SQLite database so they survive between application restarts.
class SettingsRepository:

    ###########################################################################
    ###                  SettingsRepository -> __init__()                   ###
    ###########################################################################
    def __init__(
        self,
        db_path: Path,
        report_error: Callable[[str, str], None] = lambda *_: None,
    ):
        """
        Initializes the SettingsRepository, ensuring the database file and its
        settings table exist.

        Args:
            db_path (Path): Location of the SQLite database file. Injected by the
                consuming application so this repository stays application-agnostic.
            report_error (Callable[[str, str], None]): Callback used to surface a
                database failure to the user, taking an error title and message.
                Defaults to a no-op so the repository never depends on a reporter
                being wired in (the controller injects the GUI's error popup).
        """

        # Location of the SQLite database file backing this repository
        self.db_path = db_path

        # Callback used to report database failures to the user
        self.report_error = report_error

        # Create the database file and schema up front so reads/writes can assume
        # the settings table exists.
        self.initialize_database()

    ###########################################################################
    ###              SettingsRepository -> initialize_database()            ###
    ###########################################################################
    def initialize_database(self):
        """
        Ensures the data directory, database file, and settings table exist.

        The settings table is a generic key/value store so new settings can be
        added without changing the schema.
        """

        try:
            # Ensure the data directory exists before SQLite creates the file
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self.db_path) as connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS settings ("
                    "key TEXT PRIMARY KEY, "
                    "value TEXT)"
                )
        except sqlite3.Error as error:
            self.report_error(
                "Settings Error",
                f"Could not initialize the settings database at {self.db_path}: {error}",
            )

    ###########################################################################
    ###               SettingsRepository -> get_all_settings()             ###
    ###########################################################################
    def get_all_settings(self) -> dict:
        """
        Reads every persisted setting from the database.

        Returns:
            dict: A mapping of each setting key to its stored string value. Empty
                if the database is fresh or could not be read.
        """

        try:
            with sqlite3.connect(self.db_path) as connection:
                rows = connection.execute("SELECT key, value FROM settings").fetchall()
                return {key: value for key, value in rows}
        except sqlite3.Error as error:
            self.report_error(
                "Settings Error",
                f"Could not read settings from the database at {self.db_path}: {error}",
            )
            return {}

    ###########################################################################
    ###                 SettingsRepository -> save_setting()                ###
    ###########################################################################
    def save_setting(self, key: str, value: str):
        """
        Persists a single setting, inserting it or updating it if the key already
        exists.

        Args:
            key (str): The setting's identifier (e.g. "theme", "font_family").
            value (str): The setting's value to store.
        """

        try:
            with sqlite3.connect(self.db_path) as connection:
                connection.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, value),
                )
        except sqlite3.Error as error:
            self.report_error(
                "Settings Error",
                f"Could not save the setting '{key}' to the database at {self.db_path}: {error}",
            )
