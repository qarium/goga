"""Local fixtures and shared scenario helpers of the topics domain tests.

The domain tests read the status scale through the shared built-in fixture
(``tests/conftest.py``) and the lifecycle checkpoints through the platform
environment. The two outside points of a checkpoint delivery — the
installed-distributions mapping read by ``packages_distributions`` and the
``sys.modules`` entry of a ``goga_tool_*`` package — are shared through
``tests/conftest.py``, so the registry and the delivery run for real behind
every checkpoint the domain fires. The autouse reset starts every test with
an unbuilt run registry, so no subscription leaks across tests.

The scenario helpers below are the one copy the domain suites share — the
switch-resolution wiring, the ref-tree reader, the working-copy topic, the
twin scenario data, the non-interactive stdin, the hook subscription, and
the editor stub. A suite whose scenario differs materially (the deletion
resolution's year-scoped tree reads, the creation ladder's readable pipe)
keeps its own local variant and passes the difference as an argument.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest import mock

import pytest
from goga.history.statuses import StatusScale
from goga.topics import board, creation, switching
from goga.topics.git import BranchRef

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


# --- Shared scenario helpers ---


def _trees_reader(trees: dict[str, list[str]], *, root: str = ".goga/history/") -> Callable[..., list[str]]:
    """A ``read_ref_tree_paths`` stand-in answering by ref display name.

    Args:
        trees: The ref display names mapped to their tree paths.
        root: The history root the consumer reads under — the board and the
            switch resolution use the plain history root, the deletion
            resolution the year-scoped one.

    Returns:
        The reader: ``(ref, prefix)`` in, the tree paths under the root out.
    """

    def read(ref: str, prefix: str) -> list[str]:
        assert prefix == root, "the reader answers under the pinned history root only"
        return [path for path in trees.get(ref, []) if path.startswith(prefix)]

    return read


def _wire_resolution(
    monkeypatch: pytest.MonkeyPatch,
    scale: StatusScale,
    inventory: list[BranchRef],
    trees: dict[str, list[str]],
    current: str | None,
) -> None:
    """Patch the switch resolution's import points: scale, git inventory, trees, branch."""
    monkeypatch.setattr(switching, "assemble_status_scale", lambda: scale)
    monkeypatch.setattr(switching, "list_branch_refs", lambda: inventory)
    monkeypatch.setattr(switching, "resolve_current_branch_name", lambda: current)
    monkeypatch.setattr(board, "read_ref_tree_paths", _trees_reader(trees))


def _wire_mutations(monkeypatch: pytest.MonkeyPatch, clean: bool = True) -> tuple[mock.Mock, mock.Mock, mock.Mock]:
    """Patch the switch mutations at their import points in ``switching``.

    Returns:
        The cleanliness probe, the local checkout, and the remote-tracking
        branch creation — all as recording mocks.
    """
    cleanliness = mock.Mock(return_value=clean)
    checkout = mock.Mock()
    remote_creation = mock.Mock()
    monkeypatch.setattr(switching, "is_working_tree_clean", cleanliness)
    monkeypatch.setattr(switching, "checkout_local_branch", checkout)
    monkeypatch.setattr(switching, "create_branch_from_remote_tracking", remote_creation)
    return cleanliness, checkout, remote_creation


def _non_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make stdin a non-terminal — the interactive paths must abort cleanly."""
    monkeypatch.setattr(sys, "stdin", mock.Mock(**{"isatty.return_value": False}))


def _working_copy_topic(cwd: Path, year: str, slug: str, artifacts: list[str]) -> None:
    """Create the working-copy topic directory with its artifact files."""
    for artifact in artifacts:
        path = cwd / ".goga" / "history" / year / slug / artifact
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("artifact", encoding="utf-8")


def _twin_inventory() -> list[BranchRef]:
    """The design-scenario inventory: a local branch and its remote twin."""
    return [
        BranchRef(name="feat/a", remote=False),
        BranchRef(name="origin/feat/a", remote=True),
    ]


def _twin_trees() -> dict[str, list[str]]:
    """The design-scenario ref trees: one planned topic on both refs."""
    return {
        "feat/a": [".goga/history/2026/feat-a/plan.md"],
        "origin/feat/a": [".goga/history/2026/feat-a/plan.md"],
    }


def _subscribe(*subscriptions: tuple[str, Callable[..., None]]) -> Callable[[Any], None]:
    """Build a facade callback subscribing each hook on its topics action.

    Each pair is one subscription — the topics action name and the hook;
    the hook's ``__name__`` is its hook name, so the walk warnings name the
    functions the test declares.

    Args:
        subscriptions: The (action, hook) pairs to subscribe.

    Returns:
        The ``register_hooks`` callback of one fake tool package.
    """

    def register_hooks(hooks: Any) -> None:
        for action, hook in subscriptions:
            hooks.subscribe("topics", action, hook.__name__, hook)

    return register_hooks


def _stub_edit_text(monkeypatch: pytest.MonkeyPatch, saved: str | None) -> None:
    """Stub the editor session on the creation module — a scripted save.

    Args:
        monkeypatch: the pytest patcher restoring the session on teardown.
        saved: The text the session returns — None is the cancelled entry.
    """
    monkeypatch.setattr(creation, "edit_text", lambda _initial=None: saved)
