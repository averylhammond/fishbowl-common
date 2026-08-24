import sqlite3
import pytest
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from fishbowl_common.SettingsRepository import SettingsRepository


###############################################################################
###                  SettingsRepository -> Test Fixtures                    ###
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
            the `with` statement (`connection`, the same object connect returned,
            since closing() yields what it wraps), the injected mock database path
            (`db_path`), and the mocked error reporter (`report_error`).
    """

    with patch("fishbowl_common.SettingsRepository.sqlite3.connect") as mock_connect:

        # The object bound by `with closing(sqlite3.connect(...)) as connection`.
        # closing() yields the object it wraps, so this is what connect returned.
        mock_connection = mock_connect.return_value

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


@pytest.fixture
def real_settings_repo(tmp_path):
    """
    Builds a SettingsRepository over a real SQLite file in a temporary directory,
    with nothing patched, so the SQL the other tests assert as literal strings is
    actually executed. The database path is nested one level below tmp_path so
    initialize_database() has a directory to create.

    Args:
        tmp_path (pytest.fixture): Per-test temporary directory, outside the repo

    Returns:
        types.SimpleNamespace: Holds the constructed repository (`repo`), the real
            database path (`db_path`), and the mocked error reporter
            (`report_error`), so a test can assert no failure was swallowed.
    """

    db_path = tmp_path / "data" / "settings.db"
    report_error = MagicMock()

    yield SimpleNamespace(
        repo=SettingsRepository(db_path=db_path, report_error=report_error),
        db_path=db_path,
        report_error=report_error,
    )


###############################################################################
###                    SettingsRepository -> Test Helpers                   ###
###############################################################################
def _query(db_path, sql: str) -> list:
    """
    Reads from the database file directly, so a test can inspect what the
    repository actually wrote rather than trusting the repository to report it.

    Args:
        db_path (Path): Location of the SQLite database file to read
        sql (str): The query to run

    Returns:
        list: Every row the query returned
    """

    # The same doubled `with` the repository itself uses
    with closing(sqlite3.connect(db_path)) as connection, connection:
        return connection.execute(sql).fetchall()


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


def test_init_closes_the_connection(settings_repo):
    """
    Verifies that initializing the database closes its connection rather than
    leaving it open, since sqlite3's connection context manager only commits or
    rolls back.

    Args:
        settings_repo (pytest.fixture): Provides the repository and its mocks
    """

    # The fixture's construction is the only call, so one close is expected
    settings_repo.connection.close.assert_called_once()



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


def test_initialize_database_mkdir_error_is_reported(settings_repo):
    """
    Verifies that an OSError while creating the data directory is surfaced through
    the error reporter rather than raised, since mkdir does not fail with a
    sqlite3.Error.

    Args:
        settings_repo (pytest.fixture): Provides the repository and its mocks
    """

    # The data directory cannot be created (read-only volume, permission denial)
    settings_repo.db_path.parent.mkdir.side_effect = OSError("read-only file system")

    settings_repo.repo.initialize_database()

    settings_repo.report_error.assert_called_once()

    # The failure short-circuits before SQLite, leaving only the fixture's own connect
    assert settings_repo.connect.call_count == 1


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


def test_get_all_settings_closes_the_connection(settings_repo):
    """
    Verifies that reading the settings closes its connection rather than leaving
    it open.

    Args:
        settings_repo (pytest.fixture): Provides the repository and its mocks
    """

    # Discard the close the fixture's own construction performed
    settings_repo.connection.close.reset_mock()

    settings_repo.repo.get_all_settings()

    settings_repo.connection.close.assert_called_once()



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


def test_save_setting_closes_the_connection(settings_repo):
    """
    Verifies that saving a setting closes its connection rather than leaving it
    open, which matters most here: both apps write a setting on every preference
    change.

    Args:
        settings_repo (pytest.fixture): Provides the repository and its mocks
    """

    # Discard the close the fixture's own construction performed
    settings_repo.connection.close.reset_mock()

    settings_repo.repo.save_setting("theme", "Forest")

    settings_repo.connection.close.assert_called_once()



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


def test_save_setting_closes_the_connection_on_error(settings_repo):
    """
    Verifies that a failed write still closes its connection. The connection's own
    context manager unwinds first to roll back, and this pins that the close
    wrapped around it is not skipped on the way out.

    Args:
        settings_repo (pytest.fixture): Provides the repository and its mocks
    """

    settings_repo.connection.execute.side_effect = sqlite3.Error("boom")

    # Discard the close the fixture's own construction performed
    settings_repo.connection.close.reset_mock()

    settings_repo.repo.save_setting("theme", "Forest")

    settings_repo.connection.close.assert_called_once()


###############################################################################
###            Tests SettingsRepository -> Real SQLite Behavior             ###
###############################################################################
def test_initialize_database_creates_the_settings_schema(real_settings_repo):
    """
    Verifies that constructing the repository creates the data directory and a
    settings table of two TEXT columns keyed on `key`. Every other test in this
    file mocks sqlite3 and asserts the CREATE TABLE as a string, so this is the
    only one that would fail if the schema itself were wrong.

    Args:
        real_settings_repo (pytest.fixture): Provides a repository over a real
            temporary database file
    """

    # The nested data directory was created before SQLite opened the file
    assert real_settings_repo.db_path.exists()

    # PRAGMA table_info yields (cid, name, type, notnull, default, pk) per column
    columns = [
        (name, type_, pk)
        for _, name, type_, _, _, pk in _query(
            real_settings_repo.db_path, "PRAGMA table_info(settings)"
        )
    ]

    # Text-only storage, keyed on `key`, is the contract the consuming apps rely on
    assert columns == [("key", "TEXT", 1), ("value", "TEXT", 0)]


def test_get_all_settings_on_a_fresh_database_returns_empty(real_settings_repo):
    """
    Verifies that a freshly created database reads back as no settings, and that
    the empty dict is the success path rather than a swallowed database failure.

    Args:
        real_settings_repo (pytest.fixture): Provides a repository over a real
            temporary database file
    """

    assert real_settings_repo.repo.get_all_settings() == {}

    real_settings_repo.report_error.assert_not_called()


def test_save_then_get_all_settings_round_trips_values(real_settings_repo):
    """
    Verifies that settings written through save_setting come back from
    get_all_settings unchanged, which is the round trip the consuming apps make
    across a restart.

    Args:
        real_settings_repo (pytest.fixture): Provides a repository over a real
            temporary database file
    """

    real_settings_repo.repo.save_setting("theme", "Ocean")
    real_settings_repo.repo.save_setting("font_size", "14")

    assert real_settings_repo.repo.get_all_settings() == {
        "theme": "Ocean",
        "font_size": "14",
    }

    real_settings_repo.report_error.assert_not_called()


def test_save_setting_updates_an_existing_key_in_place(real_settings_repo):
    """
    Verifies that saving a key that already exists replaces its value rather than
    inserting a second row, which is what the ON CONFLICT clause buys: both apps
    write the same handful of keys on every preference change.

    Args:
        real_settings_repo (pytest.fixture): Provides a repository over a real
            temporary database file
    """

    real_settings_repo.repo.save_setting("theme", "Ocean")
    real_settings_repo.repo.save_setting("theme", "Forest")

    # The stored value is the second one
    assert real_settings_repo.repo.get_all_settings() == {"theme": "Forest"}

    # get_all_settings returns a dict and would hide a duplicate, so the row count
    # is read from the table itself
    assert _query(real_settings_repo.db_path, "SELECT COUNT(*) FROM settings") == [(1,)]

    real_settings_repo.report_error.assert_not_called()
