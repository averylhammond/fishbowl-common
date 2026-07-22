import sqlite3
import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from fishbowl_common.SettingsRepository import SettingsRepository


###############################################################################
###                   SettingsRepository -> Test Fixture                    ###
###############################################################################
@pytest.fixture
def settings_repo():
    """
    Builds a SettingsRepository with sqlite3 mocked and a mock database path
    injected, so no real database file is created or touched. The sqlite3.connect
    patch stays active for the duration of each test so methods that open their own
    connection also run against the mock.

    Returns:
        types.SimpleNamespace: Holds the constructed repository (`repo`), the
            patched sqlite3.connect (`connect`), the connection object yielded by
            the `with` statement (`connection`), the injected mock database path
            (`db_path`), and the mocked error reporter (`report_error`).
    """

    with patch("fishbowl_common.SettingsRepository.sqlite3.connect") as mock_connect:

        # The object bound by `with sqlite3.connect(...) as connection`
        mock_connection = mock_connect.return_value.__enter__.return_value

        # The database path is injected rather than imported, so a mock stands in
        # for it and lets tests assert on the directory-creation call.
        mock_db_path = MagicMock()

        report_error = MagicMock()
        repo = SettingsRepository(db_path=mock_db_path, report_error=report_error)

        yield SimpleNamespace(
            repo=repo,
            connect=mock_connect,
            connection=mock_connection,
            db_path=mock_db_path,
            report_error=report_error,
        )


###############################################################################
###             Tests SettingsRepository -> initialize_database()           ###
###############################################################################
def test_init_creates_data_dir_and_settings_table(settings_repo):
    """
    Verifies that constructing the repository ensures the data directory exists and
    creates the settings table if it is not already present.

    Args:
        settings_repo (pytest.fixture): Provides the repository and its mocks
    """

    # The data directory is created before SQLite opens the database file
    settings_repo.db_path.parent.mkdir.assert_called_once_with(
        parents=True, exist_ok=True
    )

    # The settings table is created if it does not already exist
    settings_repo.connection.execute.assert_called_once_with(
        "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
    )


def test_initialize_database_error_is_reported(settings_repo):
    """
    Verifies that a sqlite3 failure while initializing the database is surfaced
    through the error reporter rather than raised.

    Args:
        settings_repo (pytest.fixture): Provides the repository and its mocks
    """

    # The next database operation fails
    settings_repo.connection.execute.side_effect = sqlite3.Error("boom")

    # Re-running initialization should swallow the error and report it
    settings_repo.repo.initialize_database()

    settings_repo.report_error.assert_called_once()


###############################################################################
###               Tests SettingsRepository -> get_all_settings()            ###
###############################################################################
def test_get_all_settings_returns_mapping(settings_repo):
    """
    Verifies that get_all_settings selects every row and returns the keys and
    values as a dict.

    Args:
        settings_repo (pytest.fixture): Provides the repository and its mocks
    """

    # The database returns two stored settings
    settings_repo.connection.execute.return_value.fetchall.return_value = [
        ("theme", "Ocean"),
        ("font_size", "14"),
    ]

    result = settings_repo.repo.get_all_settings()

    # The rows are returned as a key/value dict
    assert result == {"theme": "Ocean", "font_size": "14"}
    settings_repo.connection.execute.assert_called_with(
        "SELECT key, value FROM settings"
    )


def test_get_all_settings_empty_returns_empty_dict(settings_repo):
    """
    Verifies that get_all_settings returns an empty dict when the database holds no
    settings.

    Args:
        settings_repo (pytest.fixture): Provides the repository and its mocks
    """

    settings_repo.connection.execute.return_value.fetchall.return_value = []

    assert settings_repo.repo.get_all_settings() == {}


def test_get_all_settings_error_reports_and_returns_empty(settings_repo):
    """
    Verifies that a sqlite3 failure while reading settings is reported and results
    in an empty dict rather than an exception.

    Args:
        settings_repo (pytest.fixture): Provides the repository and its mocks
    """

    settings_repo.connection.execute.side_effect = sqlite3.Error("boom")

    result = settings_repo.repo.get_all_settings()

    assert result == {}
    settings_repo.report_error.assert_called_once()


###############################################################################
###                Tests SettingsRepository -> save_setting()               ###
###############################################################################
def test_save_setting_upserts_key_and_value(settings_repo):
    """
    Verifies that save_setting issues an upsert with the given key and value so an
    existing setting is updated rather than duplicated.

    Args:
        settings_repo (pytest.fixture): Provides the repository and its mocks
    """

    settings_repo.repo.save_setting("theme", "Forest")

    settings_repo.connection.execute.assert_called_with(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        ("theme", "Forest"),
    )


def test_save_setting_error_is_reported(settings_repo):
    """
    Verifies that a sqlite3 failure while saving a setting is surfaced through the
    error reporter rather than raised.

    Args:
        settings_repo (pytest.fixture): Provides the repository and its mocks
    """

    settings_repo.connection.execute.side_effect = sqlite3.Error("boom")

    settings_repo.repo.save_setting("theme", "Forest")

    settings_repo.report_error.assert_called_once()
