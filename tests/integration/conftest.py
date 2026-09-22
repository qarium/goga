"""Shared fixtures of the integration suites — the hooks platform boundary.

Re-exports the two boundary fixtures of the hooks platform tests
(``pin_package_environment`` / ``install_tool_package``) so the integration
suites pin the same two outside-world points — the ``packages_distributions``
read and the ``sys.modules`` entry of a fake ``goga_tool_*`` package — with
the platform delivery under test running for real.
"""

from tests.hooks.conftest import install_tool_package, pin_package_environment  # noqa: F401
