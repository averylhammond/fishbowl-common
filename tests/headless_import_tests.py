import builtins
import importlib
import sys
from unittest.mock import patch

import pytest


###############################################################################
###                    Headless Import -> Test Helpers                      ###
###############################################################################
def _reimport_without_tkinter(module_name: str):
    """
    Imports a module with tkinter made unavailable, mimicking a machine where the
    Tcl/Tk libraries are not installed. Any module already imported from the
    package (including tkinter itself) is dropped from sys.modules first, so the
    import under test really re-executes rather than returning a cached module.

    Args:
        module_name (str): The dotted module name to import.

    Returns:
        types.ModuleType: The freshly imported module.
    """

    real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name == "tkinter" or name.startswith("tkinter."):
            raise ImportError("No module named 'tkinter'")
        return real_import(name, *args, **kwargs)

    cached = {
        key: value
        for key, value in sys.modules.items()
        if key == "tkinter" or key.startswith(("tkinter.", "fishbowl_common"))
    }
    for key in cached:
        del sys.modules[key]

    try:
        with patch.object(builtins, "__import__", side_effect=_blocked_import):
            return importlib.import_module(module_name)
    finally:
        for key in [
            key
            for key in sys.modules
            if key == "tkinter" or key.startswith(("tkinter.", "fishbowl_common"))
        ]:
            del sys.modules[key]
        sys.modules.update(cached)


###############################################################################
###                    Tests Headless Import -> Package                     ###
###############################################################################
def test_top_level_package_imports_without_tkinter():
    """
    Verifies that the top-level package imports on a machine with no tkinter, and
    that all four infrastructure classes are still reachable from it. A consuming
    application's integration test runs headless on a machine with no display, so
    pulling tkinter in from fishbowl_common/__init__.py would break it.
    """

    module = _reimport_without_tkinter("fishbowl_common")

    assert module.ArgumentProvider is not None
    assert module.SettingsRepository is not None
    assert module.UpdateChecker is not None

    # UpdateCoordinator drives a GUI window but is typed against a Protocol, so
    # it belongs to this half of the package rather than the tkinter half
    assert module.UpdateCoordinator is not None


def test_gui_subpackage_requires_tkinter():
    """
    Verifies that the GUI subpackage is the half that needs tkinter, which is what
    the [gui] extra marks. Together with the test above this pins the split: the
    dependency lives below fishbowl_common.gui and nowhere else.
    """

    with pytest.raises(ImportError):
        _reimport_without_tkinter("fishbowl_common.gui")
