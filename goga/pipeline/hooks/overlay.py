"""Authored-wins workflow overlay: tools fill unset slots and add unnamed stages."""

from __future__ import annotations

from dataclasses import dataclass

from ..workflow import WorkflowDocument, WorkflowExtendStage, WorkflowMemory, WorkflowStage

_STAGE_FIELDS: tuple[str, ...] = (
    "agent",
    "prompt",
    "loop",
    "skills",
    "skip",
    "approve",
    "manual",
    "notes",
    "reflect",
    "memory",
)
"""The ``WorkflowStage`` field set in declaration order."""

_STAGE_DEFAULTS: dict[str, object] = dict.fromkeys(_STAGE_FIELDS)
_STAGE_DEFAULTS["skip"] = False
"""The unset stage shape — every field ``None`` except ``skip=False``."""


@dataclass(kw_only=True)
class ToolContribution:
    """One tool's committed contribution to the effective workflow.

    Args:
        tool: the platform-assigned identity of the contributing tool.
        document: the tool's declarative contribution — instructions only,
            carried verbatim into the merge.
    """

    tool: str
    document: WorkflowDocument


@dataclass(kw_only=True)
class WorkflowOverlay:
    """The composed effective workflow and its committed-tool provenance.

    Args:
        workflow: the effective workflow — the authored document with the
            committed contributions applied — or ``None`` only in the
            passthrough case (no authored workflow and nothing committed).
        provenance: the tools whose contributions committed, in enumeration
            order.
    """

    workflow: WorkflowDocument | None
    provenance: list[str]


def _is_set(field: str, value: object) -> bool:
    """Report whether a stage field carries authored intent (the SET table).

    Args:
        field: the ``WorkflowStage`` field name.
        value: the field value to classify.

    Returns:
        Whether the value represents authored intent — set when the value is
        not ``None`` (both ``manual`` states count as intent), except ``skip``
        where only ``True`` counts (``False`` is the model default).
    """
    if field == "skip":
        return value is True

    return value is not None


def _merge_stage(
    base: WorkflowDocument | None,
    name: str,
    contributions: list[ToolContribution],
) -> WorkflowStage:
    """Merge one stage name over the authored entry and every contribution.

    Args:
        base: the authored workflow, or ``None`` when no workflow resolved.
        name: the stage name to merge.
        contributions: the committed contributions, in enumeration order.

    Returns:
        The merged stage for ``name`` — a fresh :class:`WorkflowStage`; the
        inputs are never mutated.
    """
    authored = base.stages.get(name) if base is not None else None

    if authored is not None:
        values: dict[str, object] = {field: getattr(authored, field) for field in _STAGE_FIELDS}
    else:
        values = dict(_STAGE_DEFAULTS)

    authored_set = {field: _is_set(field, values[field]) for field in _STAGE_FIELDS}

    for contribution in contributions:
        tool_stage = contribution.document.stages.get(name)

        if tool_stage is None:
            continue

        for field in _STAGE_FIELDS:
            if _is_set(field, getattr(tool_stage, field)) and not authored_set[field]:
                values[field] = getattr(tool_stage, field)

    return WorkflowStage(**values)  # type: ignore[arg-type]


def _merge_prompt(base: WorkflowDocument | None, contributions: list[ToolContribution]) -> str | None:
    """Join the non-empty prompt texts with a single blank line.

    Args:
        base: the authored workflow, or ``None`` when no workflow resolved.
        contributions: the committed contributions, in enumeration order.

    Returns:
        The merged top-level prompt, or ``None`` — authored text first, then
        the contributions in enumeration order; every empty text is dropped.
    """
    texts: list[str] = []

    if base is not None and base.prompt:
        texts.append(base.prompt)

    for contribution in contributions:
        if contribution.document.prompt:
            texts.append(contribution.document.prompt)

    return "\n\n".join(texts) or None


def _merge_memory(base: WorkflowDocument | None, contributions: list[ToolContribution]) -> WorkflowMemory | None:
    """Resolve the whole-block memory — authored unbeatable, else later tool (no field merging).

    Args:
        base: the authored workflow, or ``None`` when no workflow resolved.
        contributions: the committed contributions, in enumeration order.

    Returns:
        The effective memory configuration, or ``None``.
    """
    memory = base.memory if base is not None else None

    if memory is None:
        for contribution in contributions:
            if contribution.document.memory is not None:
                memory = contribution.document.memory

    return memory


def _merge_stages(base: WorkflowDocument | None, contributions: list[ToolContribution]) -> dict[str, WorkflowStage]:
    """Merge every stage name — authored names first, then fresh names.

    Args:
        base: the authored workflow, or ``None`` when no workflow resolved.
        contributions: the committed contributions, in enumeration order.

    Returns:
        The merged stages map — the authored names in their map order, then
        the fresh names in first-appearance order across the contributions.
    """
    names: list[str] = list(base.stages) if base is not None else []

    for contribution in contributions:
        for name in contribution.document.stages:
            if name not in names:
                names.append(name)

    return {name: _merge_stage(base, name, contributions) for name in names}


def _merge_extend(
    base: WorkflowDocument | None,
    contributions: list[ToolContribution],
) -> dict[str, WorkflowExtendStage]:
    """Merge the extend maps — authored names win, among tools later wins.

    Args:
        base: the authored workflow, or ``None`` when no workflow resolved.
        contributions: the committed contributions, in enumeration order.

    Returns:
        The merged extend map — the authored entries verbatim; a contribution
        entry under an authored name is dropped; a fresh name takes the later
        contributing tool's entry.
    """
    extend: dict[str, WorkflowExtendStage] = dict(base.extend) if base is not None else {}

    for contribution in contributions:
        for name, entry in contribution.document.extend.items():
            if base is not None and name in base.extend:
                continue

            extend[name] = entry

    return extend


def merge_workflow_overlay(
    base: WorkflowDocument | None,
    contributions: list[ToolContribution],
) -> WorkflowOverlay:
    """Compose the effective workflow from the authored base and the contributions.

    Requirements:
        - Do not mutate ``base``, the contributions, or their maps.
        - Do not raise — invalid shapes cannot occur (committed
          contributions are non-empty by construction; structural validation
          of the merged result belongs to ``compile_flow``).
        - ``workflow`` is ``None`` only when ``base`` is ``None`` and no
          contribution committed — a ``None`` workflow with a non-empty
          provenance never occurs.

    Args:
        base: the authored workflow post decision and post runner-skip merge,
            or ``None`` when no workflow resolved.
        contributions: the committed tool contributions, in enumeration
            order.

    Returns:
        The :class:`WorkflowOverlay` — the effective workflow and the
        committed-tool provenance; empty ``contributions`` is the passthrough
        (the passed workflow object itself returns with empty provenance),
        and ``provenance`` lists the contributing tools in enumeration order.
    """
    # Step 1 — empty contributions: the passthrough. The passed workflow
    # object itself, zero rebuild, empty provenance.
    if not contributions:
        return WorkflowOverlay(workflow=base, provenance=[])

    # Steps 2-5 — the authored-wins merge per slot: prompt, memory, stages,
    # extend. Each helper is pure; the composed document is a new instance.
    # Step 6 — provenance: the contributing tools in enumeration order.
    return WorkflowOverlay(
        workflow=WorkflowDocument(
            prompt=_merge_prompt(base, contributions),
            stages=_merge_stages(base, contributions),
            extend=_merge_extend(base, contributions),
            memory=_merge_memory(base, contributions),
        ),
        provenance=[contribution.tool for contribution in contributions],
    )
