"""Local fixtures of the topics domain tests — the scale and the hooks environment.

The domain tests read the status scale through the shared built-in fixture
(``tests/conftest.py``) and the lifecycle checkpoints through the platform
environment. The two outside points of a checkpoint delivery — the
installed-distributions mapping read by ``packages_distributions`` and the
``sys.modules`` entry of a ``goga_tool_*`` package — are shared through
``tests/conftest.py``, so the registry and the delivery run for real behind
every checkpoint the domain fires. The autouse reset starts every test with
an unbuilt run registry, so no subscription leaks across tests.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from types import ModuleType
from typing import Any
from unittest import mock

import pytest

RUN_REGISTRY_TARGET = "goga.topics.hooks.events._RUN_REGISTRY"
"""The module attribute holding the shared run registry of the zone."""

TWO_TOOL_ENVIRONMENT: dict[str, list[str]] = {
    "goga_tool_one": ["pkg-one"],
    "goga_tool_two": ["pkg-two"],
}
"""The fixed environment of the checkpoint tests — two installed tool packages."""

TOPICS_ACTIONS: tuple[str, ...] = (
    "amend_creation",
    "amend_todo_entry",
    "topic_created",
    "topic_deleted",
    "topic_published",
    "topic_switched",
    "topic_todo_entered",
)
"""The seven topics addresses a recording pass subscribes by default."""


@pytest.fixture(autouse=True)
def reset_run_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every domain test with an unbuilt run registry.

    The shared registry of the zone's ``events`` module is module state —
    without the reset, a subscription installed by one test would leak
    into every later test of the session. The reset pins the attribute to
    None, so the first checkpoint of each test performs its own single
    build over the environment that test pinned.

    Args:
        monkeypatch: the pytest patcher restoring the attribute on teardown.
    """
    monkeypatch.setattr(RUN_REGISTRY_TARGET, None)


def _tool_identity(module_name: str) -> str:
    """The tool identity of a ``goga_tool_*`` module — the platform derivation.

    Args:
        module_name: The top-level module name of the fake package.

    Returns:
        The canonical hyphen form without the ``goga_tool_`` prefix.
    """
    return module_name.removeprefix("goga_tool_").replace("_", "-")


@pytest.fixture
def recording_hooks(
    pin_package_environment: Callable[[dict[str, list[str]]], mock.MagicMock],
    install_tool_package: Callable[[str, Callable[[Any], None] | None], ModuleType],
) -> Callable[..., list[tuple[str, str, object]]]:
    """Factory: subscribe recording hooks over the topics actions.

    The environment is pinned to the fixed two-tool mapping for the
    fixture's own packages — a test pinning it explicitly overrides the
    default with its own call. Each call installs one fake tool package
    whose callback subscribes one recording hook per requested action,
    named by the action; every delivery appends ``(tool, hook_name,
    context)`` to the one shared records list — the tests assert the
    fired actions, their order, and the facts of the delivered contexts
    off that list.

    Args:
        pin_package_environment: the enumeration-boundary pinning factory.
        install_tool_package: the fake-package installing factory.

    Returns:
        The subscribing factory: one action name or a sequence of them,
        plus optionally the tool module name, in — the shared records
        list out.
    """
    pin_package_environment(TWO_TOOL_ENVIRONMENT)

    records: list[tuple[str, str, object]] = []

    def _recorder(tool: str, action: str) -> Callable[[object], None]:
        def hook(context: object) -> None:
            records.append((tool, action, context))

        return hook

    def _record(
        actions: str | Sequence[str] = TOPICS_ACTIONS,
        *,
        module_name: str = "goga_tool_one",
    ) -> list[tuple[str, str, object]]:
        selected = [actions] if isinstance(actions, str) else list(actions)
        tool = _tool_identity(module_name)

        def register_hooks(hooks: Any) -> None:
            for action in selected:
                hooks.subscribe("topics", action, action, _recorder(tool, action))

        install_tool_package(module_name, register_hooks=register_hooks)

        return records

    return _record
