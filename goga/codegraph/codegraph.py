"""Orchestrator — the prospective cell graph of the project code.

Wires the whole pipeline for one configured language: the project
configuration is loaded first (an absent file is the uninitialized-project
error), the language is validated against the supported whitelist, the
exclusion list comes from the lint section, and the discovered sources flow
through the three analysis stages in order into the renderer. The assembled
tree is then observed and extended by the installed tool packages — every
surviving node passes the node-amendment checkpoint, the committed overlays
are placed on their nodes, and the final tree passes the validation gate
before it is returned. The run is read-only, deterministic, and idempotent
— identical code and configuration produce identical trees. The caller owns
the serialization of the returned tree.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

from ..config import load_project_config
from .analysis import collect_facts, derive_units, resolve_links
from .discovery import discover_sources
from .facts import CodegraphNode
from .hooks import CodegraphHooks, GateVerdict, NodeFacts
from .render import render_graph

_SUPPORTED_LANGUAGES = ("python", "golang", "javascript", "kotlin", "swift")


def _walk_nodes(nodes: list[CodegraphNode]) -> Iterator[CodegraphNode]:
    """Yield every node of the tree in pre-order — the node, then its children.

    Args:
        nodes: One level of the node tree being walked.

    Yields:
        Every node of the subtree — the node itself before its descendants,
            in tree order.
    """
    for node in nodes:
        yield node
        yield from _walk_nodes(node.children)


def _apply_overlays(
    nodes: list[CodegraphNode],
    overlays: dict[str, dict[str, dict[str, object]]],
) -> list[CodegraphNode]:
    """Rebuild the tree with the committed overlays — records are frozen, never mutated.

    Args:
        nodes: One level of the filtered tree being rebuilt.
        overlays: The committed tools areas by cell path — a cell without an
            entry keeps the empty overlay.

    Returns:
        The rebuilt level — every node replaced with its committed overlay and
            its rebuilt children; the input records stay unchanged.
    """
    return [
        replace(node, tools=overlays.get(node.cell, {}), children=_apply_overlays(node.children, overlays))
        for node in nodes
    ]


def codegraph(
    cells: list[str] = [],  # noqa: B006 — the CODEMANIFEST contract default; never mutated
    max_depth: int | None = None,
    depends_on: list[str] = [],  # noqa: B006 — the CODEMANIFEST contract default; never mutated
) -> list[CodegraphNode]:
    """Derive the prospective cell graph of the project code and return it as an object tree.

    The assembly is amended by the installed tool packages before it is
    returned: every node surviving the filters is delivered to the
    node-amendment checkpoint with its code-derived facts — the child list
    of the complete code-derived subtree included — the committed overlays
    are placed on their nodes, and the final tree passes the validation
    gate. Filters prune the delivery exactly as they prune the output;
    with no tool packages installed every tools area is empty and the
    output is byte-identical to the run without the extension.

    Args:
        cells: Cell paths to include in the output — the matching cells plus
            their ancestor chain survive. Empty list includes all cells.
        max_depth: Maximum nesting depth of the tree; None means no limit.
        depends_on: Keep only cells whose own or any descendant dependencies
            reach at least one of the given paths.

    Returns:
        The assembled tree of ``CodegraphNode`` records — an empty project
            yields an empty list; identical code and configuration produce
            identical trees. A node's ``tools`` area is non-empty iff at
            least one tool wrote at least one fact on it; the caller owns
            the serialization.

    Raises:
        FileNotFoundError: When ``.goga/config.yml`` is absent — the
            uninitialized-project error.
        ValueError: When the configured language is outside python, golang,
            javascript, kotlin, or swift; when a source file is unparseable —
            the error names the file; when a checkpoint hard failure stops
            the walk — the message names the tool, the action, and the
            failing node cell path; or when the validation gate vetoed the
            final tree — the message lists every violation, one line per
            tool and hook.
        ImportError: When a tool package facade fails to import — the
            message names the package.
    """
    config = load_project_config()

    language = config.language

    if language not in _SUPPORTED_LANGUAGES:
        expected = ", ".join(_SUPPORTED_LANGUAGES)
        raise ValueError(f"unsupported language: {language!r}; expected one of {expected}")

    ignore = config.lint.ignore if config.lint is not None else []

    files = discover_sources(language, ignore)
    root = Path.cwd()

    facts = collect_facts(files, language)
    units = derive_units(facts, language)
    links = resolve_links(units, facts, language, root)

    tree = render_graph(units, links, cells, max_depth, depends_on)
    filters_active = bool(cells) or max_depth is not None or bool(depends_on)
    complete_index = (
        {node.cell: node for node in _walk_nodes(render_graph(units, links, [], None, []))}
        if filters_active
        else {node.cell: node for node in _walk_nodes(tree)}
    )

    if not tree:
        return []

    hooks = CodegraphHooks()
    overlays: dict[str, dict[str, dict[str, object]]] = {}

    for node in _walk_nodes(tree):
        full = complete_index[node.cell]
        node_facts = NodeFacts(
            cell=node.cell,
            types=node.types,
            dependencies=node.dependencies,
            children=[child.cell for child in full.children],
        )

        tools = hooks.amend_node(node=node_facts)

        if tools:
            overlays[node.cell] = tools

    final = _apply_overlays(tree, overlays)
    verdict: GateVerdict = hooks.validate_graph(final)

    if not verdict.approved:
        details = "\n".join(
            f"- tool {violation.tool} / hook {violation.hook}: {violation.reason}" for violation in verdict.violations
        )
        raise ValueError(f"codegraph validation failed:\n{details}")

    return final
