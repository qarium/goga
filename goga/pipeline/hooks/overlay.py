"""The authored-wins workflow overlay — composing the effective workflow.

Two data models and one Routine make up the overlay layer of the zone:
``ToolContribution`` (one tool's committed contribution), ``WorkflowOverlay``
(the composed effective workflow plus the committed-tool provenance), and
``merge_workflow_overlay`` (the pure authored-wins composition of the two).
Authored intent wins per slot — a tool never overrides what the project
author wrote; it fills what the author left unset and adds what the author
never named.
"""

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

    Every field is set when its value is not ``None`` — including the
    three-state ``manual``, where both ``True`` (force) and ``False``
    (explicit cancel) are intent. ``skip`` is the exception: ``False`` is the
    model default and means "not skipped", so only a positive ``skip=True``
    counts as set.

    Args:
        field: the ``WorkflowStage`` field name.
        value: the field value to classify.

    Returns:
        Whether the value represents authored intent.
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

    The authored entry's set fields never yield; unset fields take the later
    contributing tool's value; a name with no authored entry starts from the
    unset shape and is fully tool-defined. A fresh :class:`WorkflowStage` is
    built regardless — the inputs are never mutated.

    Args:
        base: the authored workflow, or ``None`` when no workflow resolved.
        name: the stage name to merge.
        contributions: the committed contributions, in enumeration order.

    Returns:
        The merged stage for ``name``.
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

    Authored first, then the contributions in enumeration order; every empty
    text is dropped. ``None`` when no text survives.

    Args:
        base: the authored workflow, or ``None`` when no workflow resolved.
        contributions: the committed contributions, in enumeration order.

    Returns:
        The merged top-level prompt, or ``None``.
    """
    texts: list[str] = []

    if base is not None and base.prompt:
        texts.append(base.prompt)

    for contribution in contributions:
        if contribution.document.prompt:
            texts.append(contribution.document.prompt)

    return "\n\n".join(texts) or None


def _merge_memory(base: WorkflowDocument | None, contributions: list[ToolContribution]) -> WorkflowMemory | None:
    """Resolve the whole-block memory — authored unbeatable, else later tool.

    No field-level merging: the authored block wins outright when present;
    otherwise the LATER contributing tool's block wins (last assignment).

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

    The name order is deterministic: the authored names in their map order,
    then the fresh names in first-appearance order across the contributions.

    Args:
        base: the authored workflow, or ``None`` when no workflow resolved.
        contributions: the committed contributions, in enumeration order.

    Returns:
        The merged stages map.
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

    The authored entries are kept verbatim; a contribution entry under an
    authored name is dropped; a fresh name takes the later contributing
    tool's entry.

    Args:
        base: the authored workflow, or ``None`` when no workflow resolved.
        contributions: the committed contributions, in enumeration order.

    Returns:
        The merged extend map.
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

    The authored-wins merge, per slot:

        - Empty ``contributions`` is the passthrough — the passed workflow
          object itself returns with empty provenance (the no-tool-packages
          guarantee: zero rebuild, byte-identical behavior).
        - ``prompt`` joins the non-empty texts with a single blank line —
          authored first, then the contributions in enumeration order.
        - ``memory`` is whole-block: the authored block when present is
          unbeatable; otherwise the LATER contributing tool's block wins. No
          field-level merging.
        - ``stages`` merge per name (authored names first, then fresh names
          in appearance order): authored-set fields never yield, unset fields
          take the later contributing tool's value, and a name with no
          authored entry is fully tool-defined.
        - ``extend`` keeps the authored entries; a contribution entry under
          an authored name is dropped; among tools the later entry wins per
          name.
        - ``provenance`` is the contributing tools in enumeration order.

    The merge is pure — every merged stage and the merged document are new
    instances (field values by reference, the repo's shallow-copy
    convention); ``base``, the contributions, and their maps are never
    mutated. No filesystem access, fully deterministic, and the result stays
    declarative: it compiles through the unchanged ``compile_flow``.

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
        committed-tool provenance.
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
