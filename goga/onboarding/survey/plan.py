"""The session plan layer of the survey.

The entities declared in the cell CODEMANIFEST with ``location: plan.py``:
the plan record ``SessionPlan`` and the two plan routines
``assemble_session_plan`` and ``apply_skips``. Assembly joins the core
tree with the tool question blocks in one root under the reserved-name
and local-name guards; skip application resolves every declared path and
removes the addressed subtrees as one order-independent set.
"""

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
                "dropped the repeated element %s of tool %s: %s",
                item.id,
                declaration.tool,
                "the local names of a tool block must be unique among siblings",
            )
            continue
        seen.add(item.id)
        survivors.append(item)
    return survivors


def assemble_session_plan(core: QuestionGroup, declarations: list[ToolDeclaration]) -> SessionPlan:
    """Assemble the session plan — the core tree plus the tool blocks in one root.

    The core children keep their order and come first; every declaration
    with questions appends one group named by the tool identity after
    them, in enumeration order. The core section names are reserved — a
    tool identity colliding with one drops the tool's whole block with a
    warning (the tool keeps its amendment rights); a repeated local name
    within one declaration drops that element only. The received core
    tree is never mutated — a fresh root over fresh containers carries
    the frozen originals.

    Args:
        core: The core tree built by ``core_questions``.
        declarations: The collected declarations of the run, in
            enumeration order.

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
                "dropped the block of tool %s: %s is a reserved core section name",
                declaration.tool,
                declaration.tool,
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

    The resolution runs against the original tree only: a descendant of
    an already-skipped node still resolves here and is absorbed by the
    set application later. The rule is three-way — a path whose first
    segment names a participating tool addresses that tool's block (the
    declaring tool included); else a core section name addresses the core
    tree from the root; else a local name of the declaring tool's own
    block addresses the block under the tool identity; anything else is
    a no-op announced with a warning.

    Args:
        root: The plan root — the original, pre-removal tree.
        tools: The participating tools of the plan.
        core_section_ids: The core section names, derived from the root.
        tool: The declaring tool identity.
        raw_path: The declared path — unprefixed or tool-prefixed.

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
            "ignored the skip path %s of tool %s: %s",
            raw_path,
            tool,
            "its first segment names no tool block, core section, or own-block element",
        )
        return None

    if not _node_exists(root, address):
        logger.warning(
            "ignored the skip path %s of tool %s: %s",
            raw_path,
            tool,
            "the resolved path reaches no node of the session plan",
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

    Every path resolves against the original root and the resolved nodes
    are removed as one set — the result never depends on the order of
    application, and a descendant of a removed node is silently absorbed.
    The rebuild touches only the branches along a removal: new groups
    carry the pruned children, the frozen originals are shared elsewhere.
    The returned plan keeps the same tools list — an emptied block stays.

    Args:
        plan: The assembled plan.
        skips: The declared skips — the declaring tool identity and the
            raw path.

    Returns:
        The plan with the skipped subtrees removed.
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
