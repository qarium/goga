"""Authored-wins workflow overlay: tools fill unset slots and add unnamed stages."""

from __future__ import annotations

from dataclasses import dataclass

from ..workflow import (
    WorkflowAssistant,
    WorkflowDelegation,
    WorkflowDocument,
    WorkflowExtendStage,
    WorkflowMemory,
    WorkflowRepeat,
    WorkflowStage,
)

_STAGE_FIELDS: tuple[str, ...] = (
    "agent",
    "env",
    "prompt",
    "loop",
    "skills",
    "skip",
    "approve",
    "manual",
    "notes",
    "reflect",
    "memory",
    "assistants",
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


def _is_assistant_declaration(entry: WorkflowAssistant) -> bool:
    """Report whether ``entry`` authors declaration content (the entry-form discriminator).

    Args:
        entry: One attachment entry (or catalog entry) of the workflow. The
            discriminator is PRESENCE, not truthiness — ``prompt: ""`` and
            ``skills: []``/``env: {}`` are authored values that make the
            entry a declaration; a reference carries none of the five
            declaration fields.

    Returns:
        ``True`` when any of the five declaration fields is authored —
        ``prompt``, ``skills``, ``agent``, ``delegate``, or ``env``. With
        the presence discipline every authored declaration key leaves a
        non-``None`` value, so this is exactly the parse-time key-set
        discrimination (keys within ``{gate, when}`` ⇔ reference) — the
        one-line declaration rule shared by every consuming cell.
    """
    return (
        entry.prompt is not None
        or entry.skills is not None
        or entry.agent is not None
        or entry.delegate is not None
        or entry.env is not None
    )


def _override_entry(authored: WorkflowAssistant, base: WorkflowAssistant) -> WorkflowAssistant:
    """Compose one override entry — the authored fields over the delivered base.

    Args:
        authored: The authored entry — the override layer; every field it
            carries wins (presence decides, never truthiness).
        base: The winning delivered entry — every field the author left
            unset flows from it.

    Returns:
        A fresh :class:`WorkflowAssistant` — ``prompt``/``skills``/
        ``agent``/``delegate``/``env`` take the authored value when not
        ``None``, else the base value; ``gate``/``when`` are always the
        authored ones (attachment parameters). The inputs are never
        mutated and no content field merges partially — a field replaces
        whole (the field unit is the merge unit).
    """
    return WorkflowAssistant(
        name=authored.name,
        prompt=authored.prompt if authored.prompt is not None else base.prompt,
        skills=authored.skills if authored.skills is not None else base.skills,
        agent=authored.agent if authored.agent is not None else base.agent,
        delegate=authored.delegate if authored.delegate is not None else base.delegate,
        env=authored.env if authored.env is not None else base.env,
        gate=authored.gate,
        when=authored.when,
    )


def _fill_unset_env_keys(
    current: dict[str, str],
    tool_env: dict[str, str],
    authored: dict[str, str],
) -> dict[str, str]:
    """Fill the env keys the author left unset from one tool's env map.

    Args:
        current: the accumulated env map — the authored keys plus any
            earlier-tool fills.
        tool_env: the contributing tool's env map.
        authored: the authored env map — its key set is locked.

    Returns:
        The next accumulated map — the authored entries verbatim and, for
        the keys the author left unset, the tool's value (a later tool wins
        per key over an earlier fill).
    """
    fills = {key: value for key, value in tool_env.items() if key not in authored}

    return {**current, **fills}


def _merge_stage(
    base: WorkflowDocument | None,
    name: str,
    contributions: list[ToolContribution],
    namespace: set[str],
    winning: dict[str, WorkflowAssistant],
) -> WorkflowStage:
    """Merge one stage name over the authored entry and every contribution.

    Args:
        base: the authored workflow, or ``None`` when no workflow resolved.
        name: the stage name to merge.
        contributions: the committed contributions, in enumeration order.
        namespace: the evolving assistant namespace — the authored seed grown
            by the catalog merge; accepted appended declarations join it so
            later stages see them.
        winning: the winning delivered catalog entry per name — threaded to
            :func:`_merge_stage_assistants` for the in-place overrides.

    Returns:
        The merged stage for ``name`` — a fresh :class:`WorkflowStage`; the
        inputs are never mutated. Authored env entries are unbeatable per
        key; a tool fills only the keys the author left unset. The
        ``assistants`` field is the contract carve-out: it merges through
        :func:`_merge_stage_assistants` (override-in-place plus
        append-with-dedup), never through the authored-wins field loop.
    """
    authored = base.stages.get(name) if base is not None else None

    if authored is not None:
        values: dict[str, object] = {field: getattr(authored, field) for field in _STAGE_FIELDS}
    else:
        values = dict(_STAGE_DEFAULTS)

    authored_set = {field: _is_set(field, values[field]) for field in _STAGE_FIELDS}
    authored_env = values["env"] if authored_set["env"] else None

    for contribution in contributions:
        tool_stage = contribution.document.stages.get(name)

        if tool_stage is None:
            continue

        for field in _STAGE_FIELDS:
            if field == "assistants":
                continue

            tool_value = getattr(tool_stage, field)

            if not _is_set(field, tool_value):
                continue

            if not authored_set[field]:
                values[field] = tool_value
            elif field == "env":
                values["env"] = _fill_unset_env_keys(values["env"], tool_value, authored_env)

    values["assistants"] = _merge_stage_assistants(values["assistants"], name, contributions, namespace, winning)

    return WorkflowStage(**values)  # type: ignore[arg-type]


def _merge_stage_assistants(
    authored_map: dict[str, WorkflowAssistant] | None,
    stage_name: str,
    contributions: list[ToolContribution],
    namespace: set[str],
    winning: dict[str, WorkflowAssistant],
) -> dict[str, WorkflowAssistant] | None:
    """Merge one stage's assistant attachments — in-place overrides, then append-with-dedup.

    Args:
        authored_map: the authored attachment map, or ``None`` when the
            author attached nothing.
        stage_name: the stage name whose entries merge.
        contributions: the committed contributions, in enumeration order.
        namespace: the evolving assistant namespace — an appended
            DECLARATION whose name is already in it is dropped (the
            document-wide invariant); accepted declarations join it.
        winning: the winning delivered catalog entry per name (the later
            tool's whole entry among the contributions).

    Returns:
        The merged attachment map — the authored entries in authored
        order, then the accepted contribution entries in first-appearance
        enumeration order — or ``None`` when nothing survives. An authored
        DECLARATION whose name carries a winning delivered entry is
        replaced in place with its :func:`_override_entry` composition —
        position preservation: the authored stage keeps the landing, the
        delivered entry contributes field values only. Every append
        collision is a silent drop: a name already on the stage drops
        every entry kind; the namespace drops appended declarations only
        (references never collide across stages).
    """
    result: dict[str, WorkflowAssistant] = dict(authored_map) if authored_map is not None else {}

    for name, entry in list(result.items()):
        if _is_assistant_declaration(entry) and name in winning:
            result[name] = _override_entry(entry, winning[name])

    present_on_stage = set(result)

    for contribution in contributions:
        tool_stage = contribution.document.stages.get(stage_name)

        if tool_stage is None or tool_stage.assistants is None:
            continue

        for name, entry in tool_stage.assistants.items():
            if name in present_on_stage:
                continue

            if _is_assistant_declaration(entry) and name in namespace:
                continue

            result[name] = entry
            present_on_stage.add(name)

            if _is_assistant_declaration(entry):
                namespace.add(name)

    return result or None


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


def _merge_delegation(
    base: WorkflowDocument | None,
    contributions: list[ToolContribution],
) -> WorkflowDelegation | None:
    """Resolve the whole-block delegation — authored unbeatable, else later tool (no field merging).

    Args:
        base: the authored workflow, or ``None`` when no workflow resolved.
        contributions: the committed contributions, in enumeration order.

    Returns:
        The effective delegation block, or ``None``.
    """
    delegation = base.delegation if base is not None else None

    if delegation is None:
        for contribution in contributions:
            if contribution.document.delegation is not None:
                delegation = contribution.document.delegation

    return delegation


def _merge_repeat(
    base: WorkflowDocument | None,
    contributions: list[ToolContribution],
) -> WorkflowRepeat | None:
    """Resolve the whole-block repeat — authored unbeatable, else later tool (no field merging).

    Args:
        base: the authored workflow, or ``None`` when no workflow resolved.
        contributions: the committed contributions, in enumeration order.

    Returns:
        The effective repeat block, or ``None``. The block rides the merge
        verbatim and whole — the merge never interprets the cycle bounds
        (the consumer and the engine own the cycle semantics).
    """
    repeat = base.repeat if base is not None else None

    if repeat is None:
        for contribution in contributions:
            if contribution.document.repeat is not None:
                repeat = contribution.document.repeat

    return repeat


def _authored_namespace(base: WorkflowDocument | None) -> set[str]:
    """Seed the assistant namespace — the authored catalog and inline declarations.

    Args:
        base: the authored workflow, or ``None`` when no workflow resolved.

    Returns:
        The seed name set — every authored catalog name plus the name of
        every inline declaration on an authored stage (the five-field
        declaration rule); the authored surface owns these names, so a
        delivered catalog entry under one never lands as a fresh catalog
        name — it merges beneath the authored entry instead.
    """
    namespace = set(base.assistants) if base is not None else set()

    if base is not None:
        for stage in base.stages.values():
            for entry in (stage.assistants or {}).values():
                if _is_assistant_declaration(entry):
                    namespace.add(entry.name)

    return namespace


def _merge_catalog(
    base: WorkflowDocument | None,
    contributions: list[ToolContribution],
    namespace: set[str],
) -> tuple[dict[str, WorkflowAssistant], dict[str, WorkflowAssistant]]:
    """Merge the assistant catalogs — authored fields override, fresh names arrive verbatim.

    Args:
        base: the authored workflow, or ``None`` when no workflow resolved.
        contributions: the committed contributions, in enumeration order.
        namespace: the authored seed — every authored catalog name plus the
            authored inline-declaration names (mutated in place): every
            merged name joins it, so the stage pass that follows sees the
            whole catalog.

    Returns:
        The pair ``(merged, winning)``. ``winning`` is the winning
        delivered entry per name — the later tool's WHOLE entry among the
        contributions (no field-level merging between tools); the stage
        pass threads it to its in-place overrides. ``merged`` is the
        merged catalog: the authored names in authored order, each
        composed through :func:`_override_entry` over the winning entry
        when one is delivered under the name (an authored field replaces
        whole, an omitted field flows from the base), else verbatim; then
        the fresh delivered names verbatim (the winning entry) in
        first-appearance order. A delivered name under an authored inline
        declaration stays off the catalog — the authored surface owns the
        landing (the stage pass overrides in place).
    """
    winning: dict[str, WorkflowAssistant] = {}

    for contribution in contributions:
        for name, entry in contribution.document.assistants.items():
            winning[name] = entry

    authored_seed = set(namespace)
    merged: dict[str, WorkflowAssistant] = {}

    if base is not None:
        for name, entry in base.assistants.items():
            merged[name] = _override_entry(entry, winning[name]) if name in winning else entry

    for contribution in contributions:
        for name in contribution.document.assistants:
            if name in winning and name not in authored_seed and name not in merged:
                merged[name] = winning[name]

    namespace.update(merged)

    return merged, winning


def _merge_stages(
    base: WorkflowDocument | None,
    contributions: list[ToolContribution],
    namespace: set[str],
    winning: dict[str, WorkflowAssistant],
) -> dict[str, WorkflowStage]:
    """Merge every stage name — authored names first, then fresh names.

    Args:
        base: the authored workflow, or ``None`` when no workflow resolved.
        contributions: the committed contributions, in enumeration order.
        namespace: the evolving assistant namespace — one shared set grown
            by the catalog pass and by every accepted appended declaration,
            so a name declared on an earlier stage blocks the same-name
            declaration on a later one.
        winning: the winning delivered catalog entry per name — threaded to
            every stage's in-place assistant overrides.

    Returns:
        The merged stages map — the authored names in their map order, then
        the fresh names in first-appearance order across the contributions.
    """
    names: list[str] = list(base.stages) if base is not None else []

    for contribution in contributions:
        for name in contribution.document.stages:
            if name not in names:
                names.append(name)

    return {name: _merge_stage(base, name, contributions, namespace, winning) for name in names}


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
        The rebuilt document carries the base ``profile``/``build`` verbatim;
        the stage merge covers the complete :class:`WorkflowStage` field set
        (including ``env`` — authored entries unbeatable, tools fill the
        unset keys). The collaboration arms: the catalog merge composes an
        authored entry field by field over the winning delivered entry
        (an authored field replaces whole, an omitted field flows from the
        base; fresh delivered names arrive verbatim, the later tool winning
        among tools), an authored inline declaration overrides the same way
        in place on its stage (position preservation — the authored surface
        owns the landing), the delegation block merges whole like memory,
        and the per-stage attachments append with the on-stage and
        namespace dedup — the merged document holds every assistant name
        exactly once, so it stays compilable. The repeat block merges whole
        the same way — the authored block is unbeatable, otherwise the
        later contributing tool's block wins — and rides the rebuild
        verbatim, so a tool-amended run never loses an authored cycle
        bound.
    """

    # Step 1 — empty contributions: the passthrough. The passed workflow
    # object itself, zero rebuild, empty provenance.
    if not contributions:
        return WorkflowOverlay(workflow=base, provenance=[])

    # Step 2 — the namespace seed: the authored catalog names plus the
    # inline-declaration names of the authored stages. The catalog pass
    # grows it before any stage append is considered — the cross-kind
    # collision outcome (a delivered catalog entry under an authored
    # inline declaration staying off the catalog) depends on this order.
    namespace = _authored_namespace(base)

    # Step 4a — the catalog merge first (it owns the namespace until it
    # returns and hands the winning entries to the stage pass), then the
    # whole-block delegation and repeat (4b, 4c).
    assistants, winning = _merge_catalog(base, contributions, namespace)
    delegation = _merge_delegation(base, contributions)
    repeat = _merge_repeat(base, contributions)

    # Steps 2-5 — the authored-wins merge per slot: prompt, memory, stages,
    # extend. Each helper is pure; the composed document is a new instance.
    # Step 8 — the workflow-level fields of the base (profile, build) carry
    # verbatim, exactly as memory survives the rebuild.
    # Step 6 — provenance: the contributing tools in enumeration order.
    return WorkflowOverlay(
        workflow=WorkflowDocument(
            prompt=_merge_prompt(base, contributions),
            stages=_merge_stages(base, contributions, namespace, winning),
            extend=_merge_extend(base, contributions),
            memory=_merge_memory(base, contributions),
            profile=base.profile if base is not None else None,
            build=base.build if base is not None else None,
            assistants=assistants,
            delegation=delegation,
            repeat=repeat,
        ),
        provenance=[contribution.tool for contribution in contributions],
    )
