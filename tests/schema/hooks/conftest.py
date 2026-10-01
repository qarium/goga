"""Shared fixtures of the schema hooks zone tests — the platform boundary.

Re-exports the two boundary fixtures of the hooks platform tests
(``pin_package_environment`` / ``install_tool_package``) so the zone suites pin
the same two outside-world points — the ``packages_distributions`` read and the
``sys.modules`` entry of a ``goga_tool_*`` package — with the platform code
under test running for real.
"""

from tests.hooks.conftest import install_tool_package, pin_package_environment  # noqa: F401
