"""Shared fixtures of the codegraph cell tests — the package-environment pin.

Every non-empty tree the routine builds now delivers the checkpoint through
the real registry, so an unpinned environment would make the output depend
on the machine's installed ``goga_tool_*`` packages — the autouse pin of
``tests/drift/conftest.py``, mirrored for the codegraph suite. Tests that
install a tool pin their own environment on top — the later pin wins.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _empty_package_environment(pin_package_environment) -> None:
    """Pin the package environment empty for every test of this zone.

    Every non-empty tree the codegraph routine builds now delivers the
    checkpoint through the real registry, so an unpinned environment would
    make the output depend on the machine's installed ``goga_tool_*``
    packages. Tests that install a tool pin their own environment on top —
    the later pin wins.
    """
    pin_package_environment({})
