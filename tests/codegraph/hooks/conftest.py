"""Shared fixtures of the codegraph hooks zone tests — the platform boundary.

Re-exports the two boundary fixtures of the hooks platform tests
(``pin_package_environment`` / ``install_tool_package``) so the zone suites pin
the same two outside-world points — the ``packages_distributions`` read and the
``sys.modules`` entry of a ``goga_tool_*`` package — with the platform code
under test running for real.
"""

import pytest

from tests.hooks.conftest import install_tool_package, pin_package_environment  # noqa: F401


@pytest.fixture
def node() -> object:
    """A minimal code-derived node — the shared read surface of every tool."""
    from goga.codegraph.hooks import NodeFacts

    return NodeFacts(
        cell="goga/config",
        types=["ProjectConfig"],
        dependencies={"goga/hooks": ["HookRegistry"]},
        children=["goga/config/hooks"],
    )


@pytest.fixture
def view(node: object) -> object:
    """The read-and-contribute view of one tool."""
    from goga.codegraph.hooks import NodeAmendment

    return NodeAmendment(node=node)


@pytest.fixture
def tree() -> list[object]:
    """A minimal final tree — one leaf node, no tools overlay."""
    from goga.codegraph.facts import CodegraphNode

    return [
        CodegraphNode(
            cell="goga/config",
            types=["ProjectConfig"],
            dependencies={"goga/hooks": ["HookRegistry"]},
            children=[],
        )
    ]


@pytest.fixture
def facts() -> object:
    """A minimal code-derived node — one type, one dependency, one child."""
    from goga.codegraph.hooks import NodeFacts

    return NodeFacts(
        cell="goga/config",
        types=["ProjectConfig"],
        dependencies={"goga/hooks": ["HookRegistry"]},
        children=["goga/config/hooks"],
    )
