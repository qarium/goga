"""The session plan layer of the survey."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..participation import ToolDeclaration
from ..questions import Question, QuestionGroup

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SessionPlan:
    """The assembled survey plan — one tree with the tool blocks as groups.

    Attributes:
        root: The plan root — the core sections followed by the tool
            blocks, one group per participating tool named by the tool
            identity.
        tools: The participating tools in block order.

    Requirements:
        the record is a pure value — the routines that produce it never
        mutate the received core tree; the identities of ``tools`` reserve
        the top-level answer keys of the session.
    """

    root: QuestionGroup
    tools: list[str]


def _survivors(declaration: ToolDeclaration) -> list[Question | QuestionGroup]:
    """Filter the declared items of one tool down to unique local names.

    Args:
        declaration: The delivered declaration of the tool.

    Returns:
        The declared items in declaration order; every repeated local
        name after its first occurrence is dropped with a warning naming
        the tool and the reason — the survivors of the same declaration
        stand.
    """
    survivors: list[Question | QuestionGroup] = []
    seen: set[str] = set()

    for item in declaration.questions:
        if item.id in seen:
            logger.warning(
                "dropped the repeated element",
                extra={
                    "element": item.id,
                    "tool": declaration.tool,
                    "reason": "the local names of a tool block must be unique among siblings",
                },
            )
            continue
        seen.add(item.id)
        survivors.append(item)

    return survivors


def assemble_session_plan(core: QuestionGroup, declarations: list[ToolDeclaration]) -> SessionPlan:
    """Assemble the session plan — the core tree plus the tool blocks in one root.

    Args:
        core: The core tree built by ``core_questions``.
        declarations: The collected declarations of the run, in enumeration order; a tool identity
            colliding with a reserved core section name drops its block with a warning.

    Returns:
        The assembled plan — one root whose children are the core
        sections followed by the tool blocks, and the participating tools
        in block order.
    """
    core_children = core.children or []
    children: list[Question | QuestionGroup] = list(core_children)
    reserved = {child.id for child in core_children}
    tools: list[str] = []

    for declaration in declarations:
        if not declaration.questions:
            continue
        if declaration.tool in reserved:
            logger.warning(
                "dropped the block",
                extra={
                    "tool": declaration.tool,
                    "reason": f"{declaration.tool} is a reserved core section name",
                },
            )
            continue
        children.append(
            QuestionGroup(
                id=declaration.tool,
                prompt=f"--- Tool: {declaration.tool} ---",
                children=_survivors(declaration),
            )
        )
        tools.append(declaration.tool)

    return SessionPlan(root=QuestionGroup(id="session", children=children), tools=tools)


def _own_block_locals(root: QuestionGroup, tool: str) -> set[str]:
    """Collect the local names of one tool's own block in the original root.

    Args:
        root: The plan root — the original, pre-removal tree.
        tool: The declaring tool identity.

    Returns:
        The local names of the tool's block children; an empty set when
        the tool carries no block.
    """
    for child in root.children or []:
        if child.id == tool and isinstance(child, QuestionGroup):
            return {item.id for item in child.children or []}
    return set()


def _node_exists(root: QuestionGroup, address: list[str]) -> bool:
    """Report whether the address walks to an existing node of the tree.

    Args:
        root: The plan root — the original, pre-removal tree.
        address: The resolved path from the root.

    Returns:
        True when every segment descends into an existing child — a path
        that reaches a question (a pairs node) has no children to descend
        into and never resolves.
    """
    node: Question | QuestionGroup | None = root

    for segment in address:
        if not isinstance(node, QuestionGroup) or node.children is None:
            return False
        node = next((child for child in node.children if child.id == segment), None)
        if node is None:
            return False
    return True


def _resolve_skip(
    root: QuestionGroup,
    tools: list[str],
    core_section_ids: set[str],
    tool: str,
    raw_path: str,
) -> tuple[str, ...] | None:
    """Resolve one declared skip path to its address from the root.

    Args:
        root: The plan root — the original, pre-removal tree.
        tools: The participating tools of the plan.
        core_section_ids: The core section names, derived from the root.
        tool: The declaring tool identity.
        raw_path: The declared path — unprefixed or tool-prefixed; its first segment names a tool
            or core section (addressed from the root) or an own-block local name; else a no-op.

    Returns:
        The resolved address; None when the path resolves to nothing —
        announced with a warning naming the tool and the raw path.
    """
    segments = raw_path.split(".")
    first = segments[0]

    if first in tools or first in core_section_ids:
        address = segments
    elif first in _own_block_locals(root, tool):
        address = [tool, *segments]
    else:
        logger.warning(
            "ignored the skip path",
            extra={
                "path": raw_path,
                "tool": tool,
                "reason": "its first segment names no tool block, core section, or own-block element",
            },
        )
        return None

    if not _node_exists(root, address):
        logger.warning(
            "ignored the skip path",
            extra={
                "path": raw_path,
                "tool": tool,
                "reason": "the resolved path reaches no node of the session plan",
            },
        )
        return None

    return tuple(address)


def _prune(
    node: Question | QuestionGroup,
    path: tuple[str, ...],
    removals: set[tuple[str, ...]],
) -> Question | QuestionGroup | None:
    """Rebuild one node without the removed subtrees under it.

    Args:
        node: The node to prune — a frozen original of the assembled root.
        path: The address of the node from the root.
        removals: The resolved removal set — one order-free whole.

    Returns:
        The node with the removed subtrees gone — a rebuilt group along a
        removed branch, the frozen original on an unmodified branch — or
        None when the node itself is removed.
    """
    if path in removals:
        return None

    if isinstance(node, QuestionGroup) and node.children:
        kept: list[Question | QuestionGroup] = []
        rebuilt = False

        for child in node.children:
            pruned = _prune(child, (*path, child.id), removals)
            if pruned is None:
                rebuilt = True
                continue
            if pruned is not child:
                rebuilt = True
            kept.append(pruned)
        if rebuilt:
            return QuestionGroup(id=node.id, prompt=node.prompt, children=kept)

    return node


def apply_skips(plan: SessionPlan, skips: list[tuple[str, str]]) -> SessionPlan:
    """Apply the declared skip requests to the plan.

    Args:
        plan: The assembled plan.
        skips: The declared skips — the declaring tool identity and the
            raw path.

    Returns:
        The plan with the skipped subtrees removed as one order-independent set — a descendant
        of a removed node is silently absorbed; the tools list is unchanged, so an emptied block stays.
    """
    root = plan.root
    core_section_ids = {child.id for child in root.children or []} - set(plan.tools)

    removals: set[tuple[str, ...]] = set()

    for tool, raw_path in skips:
        address = _resolve_skip(root, plan.tools, core_section_ids, tool, raw_path)
        if address is not None:
            removals.add(address)

    if not removals:
        return SessionPlan(root=root, tools=list(plan.tools))

    kept = [
        pruned
        for pruned in (_prune(child, (child.id,), removals) for child in root.children or [])
        if pruned is not None
    ]
    return SessionPlan(root=QuestionGroup(id=root.id, prompt=root.prompt, children=kept), tools=list(plan.tools))
