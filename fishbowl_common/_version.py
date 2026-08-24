# The package version, and the single source of truth for it: pyproject.toml reads
# this attribute rather than carrying its own literal, so the two can never disagree.
#
# It lives in source rather than being read back from the installed metadata with
# importlib.metadata, because both consuming apps ship as PyInstaller onefile builds.
# PyInstaller bundles modules, not .dist-info directories, unless a spec asks it to,
# so a metadata lookup that succeeds in every test run here would raise
# PackageNotFoundError inside the frozen executable -- at import time, on the apps'
# existing "from fishbowl_common import ...", and with no CI in any of the three repos
# in a position to catch it. A module attribute is visible to a frozen build, an
# editable install and a wheel alike.
#
# Keep this file to the single literal assignment: setuptools resolves the
# [tool.setuptools.dynamic] attr by parsing the module rather than importing it only
# while it stays this simple.
__version__ = "1.4.0"
