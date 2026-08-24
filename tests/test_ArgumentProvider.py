from unittest.mock import patch

from fishbowl_common.ArgumentProvider import ArgumentProvider


###############################################################################
###             Tests ArgumentProvider -> __init__() / parse_arguments()    ###
###############################################################################
@patch("sys.argv", ["main.py"])
def test_init_defaults_to_non_integration_test_mode():
    """
    Tests that constructing an ArgumentProvider with no CLI flags leaves
    integration_test_mode disabled.

    Args:
        (none) sys.argv is patched to contain no flags
    """

    # Construct the object, which parses the (empty) argument list
    argument_provider = ArgumentProvider()

    # Expect integration test mode to be off when the flag is absent
    assert argument_provider.integration_test_mode is False


@patch("sys.argv", ["main.py", "--integration-test"])
def test_init_enables_integration_test_mode_with_flag():
    """
    Tests that passing --integration-test on the command line enables
    integration_test_mode.

    Args:
        (none) sys.argv is patched to include the --integration-test flag
    """

    # Construct the object, which parses the argument list containing the flag
    argument_provider = ArgumentProvider()

    # Expect integration test mode to be on when the flag is present
    assert argument_provider.integration_test_mode is True
