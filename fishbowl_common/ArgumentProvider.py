import argparse


# ArgumentProvider class to provide script arguments to any module that needs them
class ArgumentProvider:

    ###########################################################################
    ###                   ArgumentProvider -> __init__()                    ###
    ###########################################################################
    def __init__(self, description: str = "Fishbowl desktop application"):
        """
        Initializes the ArgumentProvider object

        This includes parsing command line arguments to determine application settings

        Args:
            description (str): Program description shown in the --help output. Accepted
                as an argument so each consuming application can label its own CLI while
                sharing this parser.
        """

        # Description used when building the argument parser's --help output
        self.description = description

        # Define an integration test mode, default to False unless specified by --integration-test flag
        self.integration_test_mode = False

        self.parse_arguments()

    ###########################################################################
    ###                ArgumentProvider -> parse_arguments()                ###
    ###########################################################################
    def parse_arguments(self):
        """
        Parses command line arguments and stores them as attributes of the object.
        """

        # Parse arguments to find out if we are running in integration test mode
        parser = argparse.ArgumentParser(description=self.description)
        parser.add_argument(
            "--integration-test",
            action="store_true",
            help="Run the application in integration test mode.",
        )
        args = parser.parse_args()

        # Store the integration test mode flag
        self.integration_test_mode = args.integration_test
