"""Local constants of the topics hooks zone tests — the platform environment.

The zone consumes the hooks platform through its facade, never around it:
the only outside points of a zone test are the two the shared fixtures of
``tests/conftest.py`` already pin — the installed-distributions mapping read
by ``packages_distributions`` and the ``sys.modules`` entry of a
``goga_tool_*`` package. The fixtures themselves are inherited from
``tests/conftest.py`` and the parent ``tests/topics/conftest.py`` (the
registry reset and the recording hooks); this module only declares the fixed
two-tool environment the zone's checkpoint tests pin.
"""

from __future__ import annotations

TWO_TOOL_ENVIRONMENT: dict[str, list[str]] = {
    "goga_tool_one": ["pkg-one"],
    "goga_tool_two": ["pkg-two"],
}
"""The fixed environment of the zone tests — two installed tool packages."""
