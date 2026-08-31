"""Shared fixtures of the hooks platform tests — the environment boundary.

The platform reaches the outside world at exactly two points: the
installed-distributions mapping read by ``packages_distributions`` and the
``sys.modules`` entry of a ``goga_tool_*`` package. The fixtures below pin
those two points and nothing else — the platform code under test runs for
real.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from types import ModuleType
from typing import Any
from unittest import mock

import pytest

ENUMERATION_TARGET = "goga.hooks.tools.packages.packages_distributions"
"""The attribute the enumeration reads — the single enumeration mock point."""


@pytest.fixture
def pin_package_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[dict[str, list[str]]], mock.MagicMock]:
    """Factory: pin the installed-packages mapping the enumeration reads.

    ``mapping`` carries the shape of ``packages_distributions()`` — a
    top-level module name mapped to the distributions providing it. Names
    without the ``goga_tool_`` prefix stay in the mapping on purpose: they
    prove the filter. Returns the boundary mock, so a test can also assert
    how often the environment was read.

    Args:
        monkeypatch: the pytest patcher restoring the boundary on teardown.

    Returns:
        The pinning factory: mapping in, boundary mock out.
    """

    def _pin(mapping: dict[str, list[str]]) -> mock.MagicMock:
        boundary = mock.MagicMock(return_value=mapping)

        monkeypatch.setattr(ENUMERATION_TARGET, boundary)

        return boundary

    return _pin


@pytest.fixture
def install_tool_package(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., ModuleType]:
    """Factory: install one fake ``goga_tool_*`` package into ``sys.modules``.

    ``register_hooks`` becomes the facade callback of the package; every
    further keyword argument is set on the module verbatim (``main``,
    ``register_topic_statuses``, ...). Each call installs one package and
    each installation is undone on teardown — one restored ``sys.modules``
    entry per fake package.

    Args:
        monkeypatch: the pytest patcher restoring ``sys.modules`` on teardown.

    Returns:
        The installing factory: module name in, the installed module out.
    """

    def _install(
        module_name: str,
        register_hooks: Callable[[Any], None] | None = None,
        **attributes: Any,
    ) -> ModuleType:
        module = ModuleType(module_name)

        if register_hooks is not None:
            module.register_hooks = register_hooks

        for name, value in attributes.items():
            setattr(module, name, value)

        monkeypatch.setitem(sys.modules, module_name, module)

        return module

    return _install
