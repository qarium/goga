"""Shared fixtures of the hooks platform tests — the environment boundary.

The platform reaches the outside world at exactly two points: the
installed-distributions mapping read by ``packages_distributions`` and the
``sys.modules`` entry of a ``goga_tool_*`` package. The fixtures below pin
those two points and nothing else — the platform code under test runs for
real.

The two boundary fixtures live once in the root ``tests/conftest.py`` (visible
to every test) and are re-exported here for the hooks zone, matching the zone
shims that re-export them further.
"""

from __future__ import annotations

from tests.conftest import install_tool_package, pin_package_environment  # noqa: F401
