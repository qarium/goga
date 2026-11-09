"""The ``parse_workflow`` routine and the ``WorkflowSyntaxError`` exception."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

import yaml

from .workflow_assistant import WorkflowAssistant
from .workflow_build import WorkflowBuild
from .workflow_delegation import WorkflowDelegation
from .workflow_document import WorkflowDocument
from .workflow_extend_stage import WorkflowExtendStage
from .workflow_gate_step import WorkflowGateStep
from .workflow_gates import WorkflowGates
from .workflow_memory import WorkflowMemory
from .workflow_reflect import WorkflowReflect
from .workflow_repeat import WorkflowRepeat
from .workflow_stage import WorkflowStage

# Fixed keys of the top-level workflow mapping. Used for unknown-key rejection.
_TOP_LEVEL_KEYS = (
    "prompt",
    "stages",
    "extend",
    "memory",
    "profile",
    "build",
    "assistants",
    "delegation",
    "repeat",
    "gates",
)

# Fixed keys of a per-stage entry, in canonical order. Used both for unknown-key
# rejection and for documenting the accepted per-stage field set.
_STAGE_KEYS = (
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
    "gates",
)

# Fixed keys of the top-level ``memory`` block, in canonical order. Used for
# unknown-key rejection and for documenting the accepted block field set. The
# goga-side ``method`` selector never reaches any output — it selects the
# instruction vocabulary the per-stage entries must conform to.
_MEMORY_KEYS = ("method", "path", "max_rules", "commit", "mode")

# Fixed keys of a per-stage ``reflect`` instruction, in canonical order. Used
# for the unknown-key rejection of the instruction's own key set.
_REFLECT_KEYS = ("file", "mode")

# Accepted values of the ``memory`` block's ``method`` selector — the goga-side
# choice of the per-stage instruction vocabulary: ``reflect`` pairs with the
# per-stage ``reflect`` instruction, ``alignment`` with the per-stage ``memory``
# instruction. ``reflect`` is the default when the block is absent entirely.
_MEMORY_METHODS = ("reflect", "alignment")

# Accepted values of the project-memory access mode — shared by the block's
# ``mode`` key and a ``reflect`` instruction's ``mode`` key.
_MEMORY_MODES = ("r", "w", "rw")

# Keys extracted out of an extend-entry's body before construction: the
# positioning keys (``before``/``after``) and the inline default overrides
# (``agent``/``loop``/``approve``). Every other key passes through verbatim as
# the stage body (``depends_on``, ``skip``, ``manual``, ``notes``, ``reflect``,
# ``memory``, ``env`` and ``assistants`` never reach the body — they are
# rejected outright).
_EXTEND_BODY_EXCLUDED = ("before", "after", "agent", "loop", "approve")

# Fixed keys of the top-level ``build`` block, in canonical dotted order. Used
# for the strict unknown-key rejection at every nesting level of the block —
# the same valid-keys fragment names all six fields wherever the unknown key
# sits (root, review, or review.additional).
_BUILD_KEYS = ("agent", "env", "review.agent", "review.env", "review.additional.agent", "review.additional.env")

# Accepted values for the ``approve`` directive (per-stage AND inline extend),
# in their canonical order. ``_validate_approve`` rejects any other string with
# a message listing these values verbatim. The two INDEPENDENT effects each
# value drives (interactive suppression / ``auto_approve`` emission) are applied
# by the compiler — see ``goga/pipeline/compiler/compile_flow.py``.
#
#   "auto"   → both effects (interactive suppression + auto_approve)
#   "plan"   → interactive suppression ONLY (communication preserved, roles off)
#   "dialog" → auto_approve ONLY (roles preserved, communication off)
_APPROVE_DIRECTIVES = ("auto", "plan", "dialog")

# Fixed keys of a top-level ``assistants`` catalog entry VALUE, in canonical
# order. Used for the strict unknown-key rejection of the catalog — the name
# is the map key, and ``gate``/``when`` are attachment parameters, so
# ``name``/``gate``/``when`` are all UNKNOWN here (authoring any of them in
# the catalog is a structural error).
_ASSISTANT_CATALOG_KEYS = ("prompt", "skills", "agent", "delegate", "env")

# Fixed keys of a stage attachment's full inline declaration form, in canonical
# order — the catalog key set plus the two attachment parameters. A mapping
# value carrying any key beyond ``gate``/``when`` is a full inline declaration
# validated against THIS set; a mapping within ``gate``/``when`` is a
# reference with its attachment parameters.
_ATTACHMENT_DECLARATION_KEYS = (*_ASSISTANT_CATALOG_KEYS, "gate", "when")

# Fixed keys of the top-level ``delegation`` block, in canonical order. Used
# for unknown-key rejection; both keys are optional (an empty block is valid)
# and ``max_tasks`` materializes to 50 when not authored.
_DELEGATION_KEYS = ("depth", "max_tasks")

# Fixed keys of the top-level ``repeat`` block, in canonical order. Used for
# unknown-key rejection; both keys are optional and NO default materializes
# here — the model carries authored values only (the empty block equals
# absence).
_REPEAT_KEYS = ("max_cycles", "keep_runs")

# Fixed keys of the top-level ``gates`` settings block, in canonical order.
# Used for unknown-key rejection; every key is optional and NO default
# materializes here — the model carries authored values only (an empty block
# equals absence).
_GATES_KEYS = ("patience", "max_iterations", "fresh_correction")

# Fixed keys of a per-stage ``gates`` check step, in canonical order. Used
# for the unknown-key rejection of a step's own key set.
_GATE_STEP_KEYS = ("name", "script", "agent", "timeout", "prompt")

# Accepted values of an attachment's ``when`` parameter — the engagement
# timing vocabulary the compiler translates into the afm ``trigger`` values.
# ``message`` is the resting engagement: the engine sends no initial request,
# the helper waits for messages and stays attached after each answer.
_WHEN_VALUES = ("start", "checkpoints", "finish", "message")

# The assistant-name grammar: every authored catalog or inline-declaration
# name must fullmatch this pattern (the same character class the afm
# team-member id grammar accepts).
_ASSISTANT_NAME_PATTERN = re.compile(r"[A-Za-z0-9._-]+")

# The one reserved assistant name — afm reserves ``assistant`` internally, so
# authoring it as a catalog or inline-declaration name is a structural error.
_RESERVED_ASSISTANT_NAME = "assistant"


class WorkflowSyntaxError(ValueError):
    """Raised when a workflow-file is structurally malformed (authored-time defect)."""


def parse_workflow(text: str) -> WorkflowDocument:
    """Structurally parse a rendered workflow-file text into a ``WorkflowDocument`` — no resolution logic.

    Args:
        text: The rendered workflow-file text (the caller owns reading and
            rendering — this routine performs no file I/O).

    Returns:
        The parsed ``WorkflowDocument`` carrying declarative instructions for
        the compiler.

    Raises:
        WorkflowSyntaxError: If the text is invalid YAML, the root is not a
            mapping, an unknown top-level or per-stage key is present, a field
            has the wrong type (including a non-bool ``skip``, a non-bool
            ``manual``, or a ``notes``/``env`` that is non-mapping or carries
            a non-str value), the ``memory`` block or a memory instruction is
            malformed (non-mapping, unknown key, non-str ``method``/``path``/
            ``mode``/``reflect.file``, a value outside its domain, a
            ``max_rules`` that is not an ``int >= 1``, a non-bool ``commit`` or
            ``memory``, an invalid path shape, a missing ``reflect.file``, a
            ``mode`` authored under ``method: reflect``, a ``reflect``
            instruction under ``alignment``, or a ``memory`` instruction under
            ``reflect``), the ``profile`` key is not a str, the ``build``
            block is malformed (non-mapping block, an unknown key anywhere in
            the six-field set, a non-str agent, or a non-mapping/non-str-value
            env map), an extend-entry
            is malformed (non-mapping value, ``depends_on`` present, ``skip``
            present, ``manual`` present, ``notes`` present, ``reflect``
            present, ``memory`` present, ``env`` present, ``assistants``
            present, ``gates`` present, ``before``/``after``
            not a
            ``list[str]``, an inline
            ``agent`` not a str or ``loop`` not an ``int >= 1`` or ``approve``
            not one of ``auto``/``plan``/``dialog``, neither ``before`` nor
            ``after``), ``loop`` is
            below one, the ``assistants`` catalog is malformed (a non-mapping
            block, a non-mapping entry value, an unknown key —
            ``name``/``gate``/``when`` included —, a wrong-typed field, an
            entry with neither ``prompt`` nor ``skills``, or a key outside
            ``[A-Za-z0-9._-]`` or equal to the reserved ``assistant``), a
            per-stage ``assistants`` map is malformed (a non-mapping value, a
            non-mapping attachment value, a missing ``when``, a non-bool
            ``gate``, a ``when`` outside ``start``/``checkpoints``/``finish``/
            ``message``,
            an unknown declaration key, a wrong-typed field, a declaration
            with neither ``prompt`` nor ``skills``, or a key violating the
            name rules), a declaration name repeats across the
            catalog and every stage declaration, the ``delegation`` block is
            malformed (a non-mapping block, an unknown key, a ``depth`` that
            is not an ``int >= 0``, or a ``max_tasks`` that is not an
            ``int >= 1``), the ``repeat`` block is malformed (a non-mapping
            block, an unknown key, or a bound that is not an ``int >= 0``),
            the top-level ``gates`` block is malformed (a non-mapping block,
            an unknown key, a ``patience``/``max_iterations`` that is not an
            ``int >= 0``, or a non-bool ``fresh_correction``), a per-stage
            ``gates`` list is malformed (a non-list value, a non-mapping
            step, an unknown step key, a missing or non-str ``name``, a step
            carrying both or neither of ``script``/``agent``, a
            ``script``/``agent`` that is not a non-empty string, a non-str
            ``timeout``/``prompt``, or a ``prompt`` on a script step),
            or the workflow provides neither a top-level
            prompt, any stage entry, any extend entry, the memory block, the
            profile key, the build block, the assistants block, nor the
            delegation block, nor the repeat block, nor the gates block.
    """
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError:
        # The low-level YAML scanner error is replaced with a clean structural
        # message — the parser contract does not expose the YAML internals.
        raise WorkflowSyntaxError("invalid YAML in workflow-file") from None

    if not isinstance(loaded, dict):
        raise WorkflowSyntaxError("workflow must be a mapping")

    (
        prompt,
        stages_raw,
        extend_raw,
        memory_raw,
        profile,
        build_raw,
        assistants_raw,
        delegation_raw,
        repeat_raw,
        gates_raw,
    ) = _extract_top_level(loaded)

    memory = _build_memory(memory_raw)
    stages = _build_stages(stages_raw)
    extend = _build_extend(extend_raw)
    build = _build_build_block(build_raw)
    assistants = _build_assistant_catalog(assistants_raw)
    delegation = _build_delegation(delegation_raw)
    repeat = _build_repeat(repeat_raw)
    gates = _build_gates(gates_raw)
    _validate_instruction_correspondence(stages, memory)
    _validate_assistant_namespace(assistants, stages)

    # The empty-workflow rule counts CONTENT — prompt, stages, extend, memory,
    # the build block, the assistants catalog, the delegation block, the
    # repeat block, or the gates block. ``profile`` never rescues a workflow
    # from emptiness: activation is not content, so a ``profile:``-only
    # workflow raises here while a ``gates:``-only workflow is valid.
    if (
        prompt is None
        and not stages
        and not extend
        and memory is None
        and build is None
        and not assistants
        and delegation is None
        and repeat is None
        and gates is None
    ):
        raise WorkflowSyntaxError(
            "empty workflow — provide at least prompt, one stage, one extend entry, "
            "the memory block, the build block, the assistants block, the delegation block, "
            "the repeat block, or the gates block"
        )

    return WorkflowDocument(
        prompt=prompt,
        stages=stages,
        extend=extend,
        memory=memory,
        profile=profile,
        build=build,
        assistants=assistants,
        delegation=delegation,
        repeat=repeat,
        gates=gates,
    )


def _extract_top_level(  # noqa: C901 — one direct branch per validated top-level block
    loaded: dict[str, Any],
) -> tuple[
    str | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    str | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
]:
    """Validate the top-level mapping and split out the ten top-level blocks.

    Args:
        loaded: The YAML-parsed top-level mapping.

    Returns:
        A 10-tuple ``(prompt, stages_raw, extend_raw, memory_raw, profile,
        build_raw, assistants_raw, delegation_raw, repeat_raw, gates_raw)``
        where ``prompt`` is the
        validated top-level prompt (``None`` when absent), ``stages_raw`` is
        the raw stages mapping (``None`` when absent), ``extend_raw`` is the
        raw extend mapping (``None`` when absent), ``memory_raw`` is the raw
        memory block (``None`` when absent), ``profile`` is the validated
        profile default (``None`` when absent or empty/whitespace-only),
        ``build_raw`` is the raw build block (``None`` when absent),
        ``assistants_raw`` is the raw assistants catalog map (``None`` when
        absent), ``delegation_raw`` is the raw delegation block (``None``
        when absent), ``repeat_raw`` is the raw repeat block (``None`` when
        absent), and ``gates_raw`` is the raw gates settings block (``None``
        when absent).

    Raises:
        WorkflowSyntaxError: If a top-level key is unknown, ``prompt`` is not a
            str, ``stages`` is not a mapping, ``extend`` is not a mapping,
            ``memory`` is not a mapping, ``profile`` is not a str, ``build``
            is not a mapping, ``assistants`` is not a mapping, ``delegation``
            is not a mapping, ``repeat`` is not a mapping, or ``gates`` is
            not a mapping.
    """
    prompt: str | None = None
    stages_raw: dict[str, Any] | None = None
    extend_raw: dict[str, Any] | None = None
    memory_raw: dict[str, Any] | None = None
    profile: str | None = None
    build_raw: dict[str, Any] | None = None
    assistants_raw: dict[str, Any] | None = None
    delegation_raw: dict[str, Any] | None = None
    repeat_raw: dict[str, Any] | None = None
    gates_raw: dict[str, Any] | None = None

    for key, value in loaded.items():
        if key == "prompt":
            prompt = _validate_top_level_prompt(value)
        elif key == "stages":
            stages_raw = _validate_top_level_mapping("non-mapping stages block in workflow", value)
        elif key == "extend":
            extend_raw = _validate_top_level_mapping("non-mapping extend block in workflow", value)
        elif key == "memory":
            memory_raw = _validate_top_level_mapping("non-mapping memory block in workflow", value)
        elif key == "profile":
            profile = _validate_top_level_profile(value)
        elif key == "build":
            build_raw = _validate_top_level_mapping("non-mapping build block in workflow", value)
        elif key == "assistants":
            assistants_raw = _validate_top_level_mapping(
                "non-mapping assistants block in workflow; author the map form keyed by assistant name", value
            )
        elif key == "delegation":
            delegation_raw = _validate_top_level_mapping("non-mapping delegation block in workflow", value)
        elif key == "repeat":
            repeat_raw = _validate_top_level_mapping("non-mapping repeat block in workflow", value)
        elif key == "gates":
            gates_raw = _validate_top_level_mapping("non-mapping gates block in workflow", value)
        else:
            raise WorkflowSyntaxError(f"unknown key in workflow: {key}; valid keys: {', '.join(_TOP_LEVEL_KEYS)}")

    return (
        prompt,
        stages_raw,
        extend_raw,
        memory_raw,
        profile,
        build_raw,
        assistants_raw,
        delegation_raw,
        repeat_raw,
        gates_raw,
    )


def _validate_top_level_prompt(field_value: Any) -> str:
    """Validate the top-level ``prompt`` value and return the confirmed ``str``.

    Args:
        field_value: The raw ``prompt`` value to validate.

    Returns:
        The validated ``str``.

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not a ``str``.
    """
    if not isinstance(field_value, str):
        raise WorkflowSyntaxError("non-str value in workflow.prompt")

    return field_value


def _validate_top_level_mapping(message: str, field_value: Any) -> dict[str, Any]:
    """Validate one top-level block value as a mapping and return the confirmed ``dict``.

    Args:
        message: The exact error message raised on a non-mapping value.
        field_value: The raw block value to validate.

    Returns:
        The validated ``dict``.

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not a ``dict``, carrying
            ``message`` verbatim.
    """
    if not isinstance(field_value, dict):
        raise WorkflowSyntaxError(message)

    return field_value


def _validate_top_level_profile(field_value: Any) -> str | None:
    """Validate the top-level ``profile`` value and return the confirmed default name.

    Args:
        field_value: The raw ``profile`` value to validate.

    Returns:
        The validated profile name, or ``None`` when the value is empty or
        whitespace-only (absence — the profile default is a NAME, never blank
        space).

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not a ``str``.
    """
    if not isinstance(field_value, str):
        raise WorkflowSyntaxError("non-str value in workflow.profile")

    return field_value if field_value.strip() else None


def _build_stages(stages_raw: dict[str, Any] | None) -> dict[str, WorkflowStage]:
    """Validate every ``stages`` entry and build the ``WorkflowStage`` map.

    Args:
        stages_raw: The raw ``stages`` mapping, or ``None`` when absent.

    Returns:
        The map of stage name to validated ``WorkflowStage`` — empty when the
        block is absent; the names are NOT validated against any pipeline
        here (the compiler's strict check owns that).
    """
    if stages_raw is None:
        return {}

    return {name: _build_stage(name, value) for name, value in stages_raw.items()}


def _build_stage(name: Any, value: Any) -> WorkflowStage:
    """Validate one ``stages`` entry and build a ``WorkflowStage`` from it.

    Args:
        name: The stage-name map key (used in error messages).
        value: The raw entry value for this stage.

    Returns:
        The validated ``WorkflowStage`` — absent fields stay ``None`` except
        ``skip`` (``False``); an explicit ``memory: false``, an empty
        ``notes`` map, an empty ``env`` map, and an empty ``assistants`` map
        normalize to ``None``.

    Raises:
        WorkflowSyntaxError: If the entry value is not a mapping, an unknown
            per-stage key is present, ``agent``/``prompt`` is not a str,
            ``env`` is not a ``dict`` of ``str``→``str``, ``loop`` is not an
            ``int >= 1``, ``skills`` is not a
            ``list[str]``, ``skip`` is not a ``bool``, ``approve`` is not
            one of ``auto``/``plan``/``dialog``, ``manual`` is not a
            ``bool``, ``notes`` is not a ``dict`` of ``str``→``str``,
            ``reflect`` is malformed (see ``_build_reflect``), ``memory``
            is not a ``bool``, the ``assistants`` map is malformed (see
            ``_build_stage_assistants``), or the ``gates`` list is malformed
            (see ``_build_stage_gates``).
    """
    if not isinstance(value, dict):
        raise WorkflowSyntaxError(f"non-mapping stage {name} in workflow.stages")

    # ``_validate_stage_field`` dispatches per key and rejects unknown keys, so
    # only the valid stage keys land here — the map is then unpacked onto the
    # constructor with per-field defaults for the absent ones (``skip`` stays
    # ``False``, everything else ``None``).
    fields: dict[str, Any] = {}

    for key, field_value in value.items():
        fields[key] = _validate_stage_field(name, key, field_value)

    return WorkflowStage(
        agent=fields.get("agent"),
        env=fields.get("env"),
        prompt=fields.get("prompt"),
        loop=fields.get("loop"),
        skills=fields.get("skills"),
        skip=fields.get("skip", False),
        approve=fields.get("approve"),
        manual=fields.get("manual"),
        notes=fields.get("notes"),
        reflect=fields.get("reflect"),
        memory=fields.get("memory"),
        assistants=fields.get("assistants"),
        gates=fields.get("gates"),
    )


def _validate_stage_field(name: Any, key: Any, field_value: Any) -> Any:  # noqa: PLR0911 — one direct branch per validated stage field
    """Validate one per-stage field value and return it (normalized), else raise.

    Args:
        name: The stage-name map key (used in error messages).
        key: The per-stage field key being validated.
        field_value: The raw value paired with ``key``.

    Returns:
        The validated field value (``agent``/``prompt`` str, ``env`` a
        non-empty ``dict[str, str]`` — ``None`` when the map is empty —,
        ``loop`` int, ``skills`` list[str], ``skip`` bool, ``approve`` str
        equal to one of ``auto``/``plan``/``dialog``, ``manual`` bool,
        ``notes`` a non-empty ``dict[str, str]`` — ``None`` when the map is
        empty —, ``reflect`` a ``WorkflowReflect``, ``memory`` a bool —
        ``None`` when explicitly ``False`` —, ``assistants`` a
        ``dict[str, WorkflowAssistant]`` — ``None`` when the map is empty —,
        or ``gates`` a ``list[WorkflowGateStep]`` — ``None`` when the list
        is empty).

    Raises:
        WorkflowSyntaxError: If ``key`` is an unknown per-stage key, or the
            field value has the wrong type (non-str agent/prompt, a non-mapping
            ``env`` or one carrying a non-str value, non-int/<1
            loop, non-list[str] skills, non-bool skip, an ``approve`` that
            is not a str equal to ``auto``/``plan``/``dialog``, a non-bool
            ``manual``, ``notes`` that is non-mapping or carries a non-str
            value, a malformed ``reflect`` instruction, a non-bool
            ``memory``, a malformed ``assistants`` map — see
            ``_build_stage_assistants`` —, or a malformed ``gates`` list —
            see ``_build_stage_gates``).
    """
    scope = f"workflow.stages.{name}"

    if key in ("agent", "prompt"):
        return _validate_str_field(scope, key, field_value)
    elif key == "env":
        return _validate_stage_env(scope, field_value)
    elif key == "loop":
        return _validate_loop(scope, field_value)
    elif key == "skills":
        return _validate_skills(scope, field_value)
    elif key in ("skip", "manual"):
        # Both are strictly-bool flags sharing the same message shape; the
        # field name lands verbatim in the location fragment.
        if not isinstance(field_value, bool):
            raise WorkflowSyntaxError(f"non-bool value in {scope}.{key}")

        return field_value
    elif key in ("approve", "notes"):
        # Two scoped single-value validators sharing the stage as their
        # location; each validator owns its own message shape.
        validator = _validate_approve if key == "approve" else _validate_notes
        return validator(scope, field_value)
    elif key in ("reflect", "memory"):
        # Two scoped single-value validators sharing the stage as their
        # location; each validator owns its own message shape.
        validator = _build_reflect if key == "reflect" else _validate_memory_instruction
        return validator(name, field_value)
    elif key in ("assistants", "gates"):
        # Two stage-scoped builder validators sharing the stage name; each
        # builder owns its own message shape.
        builder = _build_stage_assistants if key == "assistants" else _build_stage_gates
        return builder(name, field_value)
    else:
        raise WorkflowSyntaxError(f"unknown key in {scope}: {key}; valid keys: {', '.join(_STAGE_KEYS)}")


def _build_stage_gates(name: Any, value: Any) -> list[WorkflowGateStep] | None:
    """Validate a per-stage ``gates`` list and build the check-step models (contract 6.1.15).

    Args:
        name: The stage-name map key (used in error messages).
        value: The raw ``gates`` value of the stage entry.

    Returns:
        The list of validated :class:`WorkflowGateStep` check steps in
        authored order, or ``None`` when the list is empty (an empty list
        equals absence).

    Raises:
        WorkflowSyntaxError: If ``value`` is not a list, or a step is
            malformed (see :func:`_validate_gate_step`).
    """
    if not isinstance(value, list):
        raise WorkflowSyntaxError(f"non-list gates in workflow.stages.{name}")

    if not value:
        # An empty list equals absence.
        return None

    return [_validate_gate_step(name, index, step) for index, step in enumerate(value)]


def _validate_gate_step(name: Any, index: int, step: Any) -> WorkflowGateStep:
    """Validate one gate step and build its ``WorkflowGateStep`` (the checks in their normative order).

    Args:
        name: The stage-name map key (used in error messages).
        index: The step's position in the authored list (used in error
            messages).
        step: The raw step value.

    Returns:
        The validated :class:`WorkflowGateStep` — exactly one of
        ``script``/``agent`` carries the authored payload (the other stays
        ``None``) and ``prompt`` is ``None`` on every script step.

    Raises:
        WorkflowSyntaxError: If the step is not a mapping, carries an unknown
            key, omits ``name`` or carries a non-str one, carries both or
            neither of ``script``/``agent``, carries a non-empty-string
            ``script``/``agent``, carries a non-str ``timeout``/``prompt``,
            or authors ``prompt`` on a script step.
    """
    scope = f"workflow.stages.{name}.gates[{index}]"

    if not isinstance(step, dict):
        raise WorkflowSyntaxError(f"non-mapping gate step in {scope}")

    _reject_unknown_gate_step_keys(scope, step)

    if "name" not in step:
        raise WorkflowSyntaxError(f"gates step without name in {scope}")

    if not isinstance(step["name"], str):
        raise WorkflowSyntaxError(f"non-str value in {scope}.name")

    if ("script" in step) == ("agent" in step):
        raise WorkflowSyntaxError(f"gates step must carry exactly one of script/agent in {scope}")

    # Exactly one of the two is authored (the exclusivity check above); the
    # payload validator owns the non-empty-string message with the authored
    # key landing verbatim in it.
    if "script" in step:
        script = _validate_gate_step_payload(scope, "script", step["script"])
        agent = None
    else:
        script = None
        agent = _validate_gate_step_payload(scope, "agent", step["agent"])

    if "timeout" in step and not isinstance(step["timeout"], str):
        raise WorkflowSyntaxError(f"non-str value in {scope}.timeout")

    if "prompt" in step and not isinstance(step["prompt"], str):
        raise WorkflowSyntaxError(f"non-str value in {scope}.prompt")

    if "prompt" in step and "script" in step:
        # The engine accepts ``prompt`` on AI steps only — the parser binds
        # it to an agent step at authoring time.
        raise WorkflowSyntaxError(f"prompt is forbidden on a script gate step in {scope}")

    return WorkflowGateStep(
        name=step["name"],
        script=script,
        agent=agent,
        timeout=step.get("timeout"),
        prompt=step.get("prompt"),
    )


def _reject_unknown_gate_step_keys(scope: str, step: dict[str, Any]) -> None:
    """Reject any key of a gate step outside the five-step key set.

    Args:
        scope: The dotted location of the step (used in error messages).
        step: The raw step mapping.

    Raises:
        WorkflowSyntaxError: If the step carries a key outside
            ``name``/``script``/``agent``/``timeout``/``prompt``.
    """
    for key in step:
        if key not in _GATE_STEP_KEYS:
            raise WorkflowSyntaxError(f"unknown key in {scope}: {key}; valid keys: {', '.join(_GATE_STEP_KEYS)}")


def _validate_gate_step_payload(scope: str, key: str, field_value: Any) -> str:
    """Validate one gate step's ``script``/``agent`` payload and return it.

    Args:
        scope: The dotted location of the step (used in error messages).
        key: The payload field name (``"script"`` or ``"agent"``) — lands
            verbatim in the error message.
        field_value: The raw payload value.

    Returns:
        The validated non-empty ``str``.

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not a ``str``, or is an
            empty ``str`` (an authored ``null`` included — the exclusivity
            check has already passed, so the key IS authored).
    """
    if not isinstance(field_value, str) or not field_value:
        raise WorkflowSyntaxError(f"{key} must be a non-empty string in {scope}")

    return field_value


def _build_extend(extend_raw: dict[str, Any] | None) -> dict[str, WorkflowExtendStage]:
    """Validate every ``extend`` entry and build the ``WorkflowExtendStage`` map.

    Args:
        extend_raw: The raw ``extend`` mapping, or ``None`` when absent.

    Returns:
        The map of stage name to validated ``WorkflowExtendStage`` — empty
        when the block is absent; the names are NOT validated against any
        pipeline here (the compiler owns the embedding).
    """
    if extend_raw is None:
        return {}

    return {name: _build_extend_stage(name, value) for name, value in extend_raw.items()}


def _build_extend_stage(name: Any, value: Any) -> WorkflowExtendStage:
    """Validate one ``extend`` entry and build a ``WorkflowExtendStage`` from it.

    Args:
        name: The stage-name map key (used in error messages).
        value: The raw entry value for this extend stage.

    Returns:
        The validated ``WorkflowExtendStage`` — every key other than
        ``before``/``after``/``agent``/``loop``/``approve`` passes through
        verbatim as the stage body.

    Raises:
        WorkflowSyntaxError: If the entry value is not a mapping, it contains a
            ``depends_on`` key, it contains a ``skip`` key, it contains a
            ``manual`` key, it contains a ``notes`` key, it contains a
            ``reflect`` key, it contains a ``memory`` key, it contains an
            ``env`` key (``env`` is valid ONLY under ``stages.<name>`` — the
            environment of a new stage is authored in the stages block by the
            new stage's name), ``before`` is not a
            ``list[str]``, ``after`` is not a ``list[str]``, an inline
            ``agent`` is not a ``str``, an inline ``loop`` is not an
            ``int >= 1``, an inline ``approve`` is not a str equal to one of
            ``auto``/``plan``/``dialog``, or neither ``before`` nor ``after`` is present
            (checked in that order).
    """
    if not isinstance(value, dict):
        raise WorkflowSyntaxError(f"non-mapping extend entry {name} in workflow.extend")

    _reject_forbidden_extend_keys(name, value)

    before = value.get("before")
    if before is not None and not _is_list_of_str(before):
        raise WorkflowSyntaxError(f"non-list-of-str before in workflow.extend.{name}")

    after = value.get("after")
    if after is not None and not _is_list_of_str(after):
        raise WorkflowSyntaxError(f"non-list-of-str after in workflow.extend.{name}")

    # Inline ``agent``/``loop``/``approve`` are DEFAULT overrides (an explicit
    # stages-block entry for the same name wins per-field in the compiler). They
    # are validated per-key WITHOUT an ``is not None`` guard: an explicit
    # ``null`` is a structural type error, not an absence (symmetric with the
    # per-stage ``agent``/``loop``/``approve`` and the extend ``loop``). Absence
    # is expressed by omitting the key, which leaves the model field ``None``.
    agent: str | None = None
    if "agent" in value:
        agent = _validate_str_field(f"workflow.extend.{name}", "agent", value["agent"])

    loop: int | None = None
    if "loop" in value:
        loop = _validate_loop(f"workflow.extend.{name}", value["loop"])

    approve: str | None = None
    if "approve" in value:
        approve = _validate_approve(f"workflow.extend.{name}", value["approve"])

    # At-least-one is the LAST structural check (contract step 6.2.10): a
    # multi-defect entry (no positioning AND a bad inline agent/loop/approve)
    # must surface the more specific type error raised above, not this
    # positional one.
    if before is None and after is None:
        raise WorkflowSyntaxError(f"extend entry {name} requires at least one of before/after")

    body = {key: entry_value for key, entry_value in value.items() if key not in _EXTEND_BODY_EXCLUDED}

    return WorkflowExtendStage(before=before, after=after, agent=agent, loop=loop, approve=approve, body=body)


def _reject_forbidden_extend_keys(name: Any, value: dict[str, Any]) -> None:
    """Reject the keys an extend-entry must never carry (contract 6.2.2 - 6.2.8, 6.8).

    Args:
        name: The stage-name map key (used in error messages).
        value: The raw entry value for this extend stage.

    Raises:
        WorkflowSyntaxError: If the entry carries ``depends_on``, ``skip``,
            ``manual``, ``notes``, ``reflect``, ``memory``, ``env``,
            ``assistants``, or ``gates`` (checked in that order).
    """
    for forbidden_key in ("depends_on", "skip", "manual", "notes", "reflect", "memory", "env", "assistants", "gates"):
        if forbidden_key in value:
            raise WorkflowSyntaxError(f"{forbidden_key} is forbidden in workflow.extend.{name}")


def _build_memory(memory_raw: dict[str, Any] | None) -> WorkflowMemory | None:
    """Validate the ``memory`` block and build the ``WorkflowMemory`` (contract 6.0).

    Args:
        memory_raw: The raw ``memory`` mapping, or ``None`` when absent.

    Returns:
        The validated ``WorkflowMemory`` with every default materialized
        (``method`` ``"reflect"``, ``max_rules`` ``25``, ``commit`` ``False``,
        ``mode`` ``"rw"`` under alignment and ``None`` under reflect), or
        ``None`` when the block is absent. No memory-root composition happens
        here — ``path`` carries the authored suffix only.

    Raises:
        WorkflowSyntaxError: If the block carries an unknown key, a value has
            the wrong type (non-str ``method``/``path``/``mode``, non-int
            ``max_rules`` — ``bool`` counts as non-int —, or a non-bool
            ``commit``), a value falls outside its domain (``method`` not one
            of ``reflect``/``alignment``, ``mode`` not one of ``r``/``w``/
            ``rw``, ``max_rules`` below one), ``path`` has an invalid shape, or
            a ``mode`` is authored together with ``method: reflect``.
    """
    if memory_raw is None:
        return None

    values: dict[str, Any] = {}

    for key, field_value in memory_raw.items():
        if key == "method":
            values["method"] = _validate_memory_method("workflow.memory", field_value)
        elif key == "path":
            values["path"] = _validate_path_shape("workflow.memory.path", field_value)
        elif key == "max_rules":
            values["max_rules"] = _validate_max_rules(field_value)
        elif key == "commit":
            if not isinstance(field_value, bool):
                raise WorkflowSyntaxError("non-bool value in workflow.memory.commit")

            values["commit"] = field_value
        elif key == "mode":
            values["mode"] = _validate_memory_mode("workflow.memory.mode", "workflow.memory", field_value)
        else:
            raise WorkflowSyntaxError(f"unknown key in workflow.memory: {key}; valid keys: {', '.join(_MEMORY_KEYS)}")

    method = values.get("method", "reflect")

    # The mode exists only for the alignment method — an authored mode under
    # the default reflect method is a structural error, not a silent ignore.
    if "mode" in values and method == "reflect":
        raise WorkflowSyntaxError("mode is forbidden in workflow.memory with method: reflect")

    return WorkflowMemory(
        method=method,
        path=values.get("path"),
        max_rules=values.get("max_rules", 25),
        commit=values.get("commit", False),
        mode=(values.get("mode", "rw") if method == "alignment" else None),
    )


def _build_reflect(name: Any, value: Any) -> WorkflowReflect:
    """Validate one ``reflect`` instruction; the method correspondence is a separate pass.

    Args:
        name: The stage-name map key (used in error messages).
        value: The raw ``reflect`` entry value.

    Returns:
        The validated ``WorkflowReflect`` — the authored ``file`` verbatim and
        the mode materialized to ``"rw"`` when the entry omits it.

    Raises:
        WorkflowSyntaxError: If the value is not a mapping, carries an unknown
            key, omits ``file``, carries a ``file`` that is not a str or not a
            valid path shape, or carries a ``mode`` that is not a str in
            ``r``/``w``/``rw``.
    """
    if not isinstance(value, dict):
        raise WorkflowSyntaxError(f"non-mapping reflect in workflow.stages.{name}")

    file_value: str | None = None
    mode_value: str | None = None

    for key, field_value in value.items():
        if key == "file":
            file_value = _validate_path_shape(f"workflow.stages.{name}.reflect.file", field_value)
        elif key == "mode":
            mode_value = _validate_memory_mode(
                f"workflow.stages.{name}.reflect.mode",
                f"workflow.stages.{name}.reflect",
                field_value,
            )
        else:
            raise WorkflowSyntaxError(
                f"unknown key in workflow.stages.{name}.reflect: {key}; valid keys: {', '.join(_REFLECT_KEYS)}"
            )

    if file_value is None:
        raise WorkflowSyntaxError(f"file is required in workflow.stages.{name}.reflect")

    return WorkflowReflect(file=file_value, mode=mode_value or "rw")


def _validate_memory_instruction(name: Any, field_value: Any) -> bool | None:
    """Validate a per-stage ``memory`` instruction; correspondence is a separate pass.

    Args:
        name: The stage-name map key (used in error messages).
        field_value: The raw ``memory`` instruction value.

    Returns:
        The instruction when ``True``, or ``None`` (absence) when ``False``.

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not a ``bool``.
    """
    if not isinstance(field_value, bool):
        raise WorkflowSyntaxError(f"non-bool value in workflow.stages.{name}.memory")

    return field_value if field_value else None


def _validate_instruction_correspondence(
    stages: dict[str, WorkflowStage],
    memory: WorkflowMemory | None,
) -> None:
    """Reject a per-stage instruction the method disallows; the default method is ``reflect``.

    Args:
        stages: The built per-stage map (name → ``WorkflowStage``).
        memory: The built memory configuration, or ``None`` when the
            workflow-file carries no block.

    Raises:
        WorkflowSyntaxError: If a stage carries a ``reflect`` instruction under
            the alignment method, or a ``memory`` instruction under the reflect
            method.
    """
    method = memory.method if memory is not None else "reflect"

    for name, stage in stages.items():
        if method == "alignment" and stage.reflect is not None:
            raise WorkflowSyntaxError(f"reflect is forbidden in workflow.stages.{name} with method: alignment")

        if method == "reflect" and stage.memory is True:
            raise WorkflowSyntaxError(f"memory is forbidden in workflow.stages.{name} with method: reflect")


def _validate_memory_method(scope: str, field_value: Any) -> str:
    """Validate the ``memory`` block's ``method`` value and return it.

    Args:
        scope: The dotted location (without the trailing ``.method``).
        field_value: The raw ``method`` value to validate.

    Returns:
        The validated method (one of ``_MEMORY_METHODS``).

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not a ``str``, or is a
            ``str`` other than ``"reflect"``/``"alignment"``.
    """
    if not isinstance(field_value, str):
        raise WorkflowSyntaxError(f"non-str value in {scope}.method")

    if field_value not in _MEMORY_METHODS:
        raise WorkflowSyntaxError(f"method must be one of: {', '.join(_MEMORY_METHODS)} in {scope}")

    return field_value


def _validate_memory_mode(value_location: str, domain_location: str, field_value: Any) -> str:
    """Validate a memory ``mode`` value and return it.

    Args:
        value_location: The dotted location used in the non-str message.
        domain_location: The dotted location used in the domain message.
        field_value: The raw ``mode`` value to validate.

    Returns:
        The validated mode (one of ``_MEMORY_MODES``).

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not a ``str``, or is a
            ``str`` other than ``"r"``/``"w"``/``"rw"``.
    """
    if not isinstance(field_value, str):
        raise WorkflowSyntaxError(f"non-str value in {value_location}")

    if field_value not in _MEMORY_MODES:
        raise WorkflowSyntaxError(f"mode must be one of: {', '.join(_MEMORY_MODES)} in {domain_location}")

    return field_value


def _validate_max_rules(field_value: Any) -> int:
    """Validate the ``memory`` block's ``max_rules`` value and return the confirmed ``int``.

    Args:
        field_value: The raw ``max_rules`` value to validate.

    Returns:
        The validated rule cap (an ``int >= 1``).

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not an ``int`` (``bool``
            counts as not-an-int), or is an ``int`` below one.
    """
    if isinstance(field_value, bool) or not isinstance(field_value, int):
        raise WorkflowSyntaxError("non-int value in workflow.memory.max_rules")

    if field_value < 1:
        raise WorkflowSyntaxError("max_rules must be >= 1 in workflow.memory")

    return field_value


def _validate_path_shape(scope: str, field_value: Any) -> str:
    """Validate a memory path value's shape and return the confirmed ``str``.

    Args:
        scope: The dotted location of the key being validated.
        field_value: The raw path value to validate.

    Returns:
        The validated path suffix, carried verbatim — never resolved against
        the memory root here (the consumer composes the final path).

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not a ``str``, is empty, is
            absolute, or contains a ``..`` segment.
    """
    if not isinstance(field_value, str):
        raise WorkflowSyntaxError(f"non-str value in {scope}")

    path = PurePosixPath(field_value)

    if field_value == "" or path.is_absolute() or ".." in path.parts:
        raise WorkflowSyntaxError(f"invalid path in {scope}: {field_value}")

    return field_value


def _is_list_of_str(value: Any) -> bool:
    """Return whether ``value`` is a ``list`` whose every element is a ``str``.

    Args:
        value: The candidate value to type-check.

    Returns:
        ``True`` when ``value`` is a ``list`` whose every element is a ``str``,
        else ``False`` — ``bool`` elements fail the ``str`` check.
    """
    return isinstance(value, list) and all(isinstance(element, str) for element in value)


def _validate_loop(scope: str, field_value: Any) -> int:
    """Validate a ``loop`` field value and return the confirmed ``int``.

    Args:
        scope: The dotted location (without the trailing ``.loop``).
        field_value: The raw ``loop`` value to validate.

    Returns:
        The validated ``loop`` count (an ``int >= 1``).

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not an ``int`` (``bool``
            counts as not-an-int), or is an ``int`` below one.
    """
    if isinstance(field_value, bool) or not isinstance(field_value, int):
        raise WorkflowSyntaxError(f"non-int value in {scope}.loop")

    if field_value < 1:
        raise WorkflowSyntaxError(f"loop must be >= 1 in {scope}")

    return field_value


def _validate_str_field(scope: str, field_name: str, field_value: Any) -> str:
    """Validate a per-stage ``str`` field (``agent``/``prompt``) and return it.

    Args:
        scope: The dotted location (without the trailing ``.{field_name}``).
        field_name: The field name (``"agent"`` or ``"prompt"``).
        field_value: The raw value to validate.

    Returns:
        The validated ``str``.

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not a ``str``.
    """
    if not isinstance(field_value, str):
        raise WorkflowSyntaxError(f"non-str value in {scope}.{field_name}")

    return field_value


def _validate_skills(scope: str, field_value: Any) -> list[str]:
    """Validate a per-stage ``skills`` value and return it verbatim.

    Args:
        scope: The dotted location (without the trailing ``.skills``).
        field_value: The raw ``skills`` value to validate.

    Returns:
        The validated list of skill names.

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not a list of str.
    """
    if not _is_list_of_str(field_value):
        raise WorkflowSyntaxError(f"non-list-of-str skills in {scope}")

    return field_value


def _validate_approve(scope: str, field_value: Any) -> str:
    """Validate an ``approve`` field value and return it.

    Args:
        scope: The dotted location (without the trailing ``.approve``).
        field_value: The raw ``approve`` value to validate.

    Returns:
        The validated directive (one of ``_APPROVE_DIRECTIVES``).

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not a ``str``, or is a
            ``str`` other than ``"auto"``/``"plan"``/``"dialog"``.
    """
    if not isinstance(field_value, str):
        raise WorkflowSyntaxError(f"non-str value in {scope}.approve")

    if field_value not in _APPROVE_DIRECTIVES:
        raise WorkflowSyntaxError(f"approve must be one of: {', '.join(_APPROVE_DIRECTIVES)} in {scope}")

    return field_value


def _validate_notes(scope: str, field_value: Any) -> dict[str, str] | None:
    """Validate a ``notes`` field value and return it (or ``None`` when empty).

    Args:
        scope: The dotted location (without the trailing ``.notes``).
        field_value: The raw ``notes`` value to validate.

    Returns:
        The validated notes map, or ``None`` when the map is empty (absence) —
        map keys are deliberately not validated (afm owns the runtime note
        grammar).

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not a ``dict``, or any of
            its values is not a ``str``.
    """
    if not isinstance(field_value, dict):
        raise WorkflowSyntaxError(f"non-mapping notes in {scope}")

    for key, text in field_value.items():
        if not isinstance(text, str):
            raise WorkflowSyntaxError(f"non-str value in {scope}.notes.{key}")

    if not field_value:
        # An empty map equals absence.
        return None

    return field_value


def _validate_stage_env(scope: str, field_value: Any) -> dict[str, str] | None:
    """Validate a per-stage ``env`` instruction and return it (or ``None`` when empty).

    Args:
        scope: The dotted location of the entry owning the ``env`` map
            (``workflow.stages.NAME`` or ``workflow.assistants.NAME``) used
            in error messages.
        field_value: The raw ``env`` value to validate.

    Returns:
        The validated env map, or ``None`` when the map is empty (absence) —
        the model carries either ``None`` or a non-empty map, mirroring the
        ``notes`` pattern the wrapper generation's ``is not None`` check
        relies on.

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not a ``dict``, any of its
            keys is not a ``str``, or any of its values is not a ``str``.
    """
    if not isinstance(field_value, dict):
        raise WorkflowSyntaxError(f"non-mapping env in {scope}")

    for key, value in field_value.items():
        if not isinstance(key, str):
            raise WorkflowSyntaxError(f"non-str key in {scope}.env")

        if not isinstance(value, str):
            raise WorkflowSyntaxError(f"non-str value in {scope}.env.{key}")

    if not field_value:
        # An empty map equals absence.
        return None

    return field_value


def _validate_assistant_env(scope: str, field_value: Any) -> dict[str, str]:
    """Validate one assistant ``env`` map and return it as authored (presence-preserving).

    Args:
        scope: The dotted location of the entry owning the ``env`` map
            (``workflow.assistants.NAME`` or
            ``workflow.stages.STAGE.assistants.NAME``).
        field_value: The raw ``env`` value to validate.

    Returns:
        The validated env map carried AS AUTHORED — an authored empty map
        returns ``{}`` (an explicit override that clears), the one
        deliberate divergence from :func:`_validate_stage_env`, whose
        empty-equals-absence rule stays reserved for the per-stage ``env``
        of :class:`WorkflowStage`.

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not a ``dict``, any of
            its keys is not a ``str``, or any of its values is not a
            ``str``.
    """
    if not isinstance(field_value, dict):
        raise WorkflowSyntaxError(f"non-mapping env in {scope}")

    for key, value in field_value.items():
        if not isinstance(key, str):
            raise WorkflowSyntaxError(f"non-str key in {scope}.env")

        if not isinstance(value, str):
            raise WorkflowSyntaxError(f"non-str value in {scope}.env.{key}")

    return field_value


def _build_build_block(build_raw: dict[str, Any] | None) -> WorkflowBuild | None:
    """Validate the top-level ``build`` block and build the ``WorkflowBuild`` (contract 6.4).

    Args:
        build_raw: The raw ``build`` mapping, or ``None`` when absent.

    Returns:
        The validated :class:`WorkflowBuild` — every one of the six fields
        ``None`` when absent (an empty env map equals absence) — or ``None``
        when the block is absent. No layering happens here — the build path
        owns the config/workflow merge.

    Raises:
        WorkflowSyntaxError: If the block carries an unknown key at any nesting
            level (the strict key set is ``agent``, ``env``, ``review.agent``,
            ``review.env``, ``review.additional.agent``,
            ``review.additional.env`` — ``proxy`` and ``hosts`` are unknown
            keys), an ``agent`` value is not a str, ``review``/``additional``
            is not a mapping, or an ``env`` map is non-mapping or carries a
            non-str key or a non-str value.
    """
    if build_raw is None:
        return None

    agent: str | None = None
    env: dict[str, str] | None = None
    review_agent: str | None = None
    review_env: dict[str, str] | None = None
    review_additional_agent: str | None = None
    review_additional_env: dict[str, str] | None = None

    for key, value in build_raw.items():
        if key == "agent":
            agent = _validate_build_agent("workflow.build", value)
        elif key == "env":
            env = _validate_build_env("workflow.build", value)
        elif key == "review":
            review_agent, review_env, review_additional_agent, review_additional_env = _build_build_review(value)
        else:
            raise _unknown_build_key_error("workflow.build", key)

    return WorkflowBuild(
        agent=agent,
        env=env,
        review_agent=review_agent,
        review_env=review_env,
        review_additional_agent=review_additional_agent,
        review_additional_env=review_additional_env,
    )


def _build_build_review(value: Any) -> tuple[str | None, dict[str, str] | None, str | None, dict[str, str] | None]:
    """Validate the ``review`` sub-block of the build block and split its four fields.

    Args:
        value: The raw ``review`` mapping.

    Returns:
        A 4-tuple ``(review_agent, review_env, review_additional_agent,
        review_additional_env)`` — each field ``None`` when absent.

    Raises:
        WorkflowSyntaxError: If ``value`` is not a mapping, carries an unknown
            key, or its nested values fail the agent/env validation (see
        :func:`_validate_build_agent` / :func:`_validate_build_env`).
    """
    if not isinstance(value, dict):
        raise WorkflowSyntaxError("non-mapping review block in workflow.build")

    review_agent: str | None = None
    review_env: dict[str, str] | None = None
    review_additional_agent: str | None = None
    review_additional_env: dict[str, str] | None = None

    for key, entry_value in value.items():
        if key == "agent":
            review_agent = _validate_build_agent("workflow.build.review", entry_value)
        elif key == "env":
            review_env = _validate_build_env("workflow.build.review", entry_value)
        elif key == "additional":
            review_additional_agent, review_additional_env = _build_build_additional(entry_value)
        else:
            raise _unknown_build_key_error("workflow.build.review", key)

    return review_agent, review_env, review_additional_agent, review_additional_env


def _build_build_additional(value: Any) -> tuple[str | None, dict[str, str] | None]:
    """Validate the ``review.additional`` sub-block and split its two fields.

    Args:
        value: The raw ``additional`` mapping.

    Returns:
        A 2-tuple ``(review_additional_agent, review_additional_env)`` — each
        field ``None`` when absent.

    Raises:
        WorkflowSyntaxError: If ``value`` is not a mapping, carries an unknown
            key, or its values fail the agent/env validation (see
        :func:`_validate_build_agent` / :func:`_validate_build_env`).
    """
    if not isinstance(value, dict):
        raise WorkflowSyntaxError("non-mapping additional block in workflow.build.review")

    review_additional_agent: str | None = None
    review_additional_env: dict[str, str] | None = None

    for key, entry_value in value.items():
        if key == "agent":
            review_additional_agent = _validate_build_agent("workflow.build.review.additional", entry_value)
        elif key == "env":
            review_additional_env = _validate_build_env("workflow.build.review.additional", entry_value)
        else:
            raise _unknown_build_key_error("workflow.build.review.additional", key)

    return review_additional_agent, review_additional_env


def _unknown_build_key_error(location: str, key: Any) -> WorkflowSyntaxError:
    """Build the strict unknown-key error of the build block at ``location``.

    Args:
        location: The dotted block location (``workflow.build``,
            ``workflow.build.review``, or ``workflow.build.review.additional``).
        key: The unknown key found at that level.

    Returns:
        The ready-to-raise ``WorkflowSyntaxError`` carrying the same
        valid-keys fragment (all six dotted fields) at every nesting level.
    """
    return WorkflowSyntaxError(f"unknown key in {location}: {key}; valid keys: {', '.join(_BUILD_KEYS)}")


def _validate_build_agent(location: str, field_value: Any) -> str:
    """Validate one build-block ``agent`` value and return the confirmed ``str``.

    Args:
        location: The dotted block location (``workflow.build``,
            ``workflow.build.review``, or ``workflow.build.review.additional``).
        field_value: The raw ``agent`` value to validate.

    Returns:
        The validated ``str``.

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not a ``str``.
    """
    if not isinstance(field_value, str):
        raise WorkflowSyntaxError(f"non-str value in {location}.agent")

    return field_value


def _validate_build_env(location: str, field_value: Any) -> dict[str, str] | None:
    """Validate one build-block ``env`` map and return it (or ``None`` when empty).

    Args:
        location: The dotted block location (``workflow.build``,
            ``workflow.build.review``, or ``workflow.build.review.additional``).
        field_value: The raw ``env`` value to validate.

    Returns:
        The validated env map, or ``None`` when the map is empty (absence) —
        the string-map pattern shared with the per-stage ``env``.

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not a ``dict``, any of its
            keys is not a ``str``, or any of its values is not a ``str``.
    """
    if not isinstance(field_value, dict):
        raise WorkflowSyntaxError(f"non-mapping env in {location}")

    for key, value in field_value.items():
        if not isinstance(key, str):
            raise WorkflowSyntaxError(f"non-str key in {location}.env")

        if not isinstance(value, str):
            raise WorkflowSyntaxError(f"non-str value in {location}.env.{key}")

    if not field_value:
        # An empty map equals absence.
        return None

    return field_value


def _build_assistant_catalog(assistants_raw: dict[str, Any] | None) -> dict[str, WorkflowAssistant]:
    """Validate the ``assistants`` catalog map and build the name-keyed map (contract 6.5).

    Args:
        assistants_raw: The raw ``assistants`` map, or ``None`` when the
            block is absent.

    Returns:
        The insertion-ordered map of assistant name to validated
        :class:`WorkflowAssistant` — empty when the block is absent (an empty
        ``assistants: {}`` map equals no catalog); every absent field stays
        ``None`` (``delegate`` included — the not-authored tri-state value),
        and an authored empty ``skills``/``env`` is carried as an explicit
        override that clears.

    Raises:
        WorkflowSyntaxError: If an entry value is not a mapping, carries an
            unknown key (``name``/``gate``/``when`` included), a field has
            the wrong type (non-str ``prompt``/``agent``, non-list-of-str
            ``skills``, non-bool ``delegate``, a malformed ``env`` map), or
            the map key violates the ``[A-Za-z0-9._-]`` grammar or equals
            the reserved ``assistant``. An entry may carry none of the five
            declaration fields — an override-style entry whose effective
            content resolves at compilation.
    """
    if assistants_raw is None:
        return {}

    catalog: dict[str, WorkflowAssistant] = {}

    # A map key cannot repeat, so no within-catalog duplicate check exists
    # here — the dict is keyed by the authored name, and the later
    # document-wide namespace walk over ``values()`` only guards the
    # cross-surface repeats (catalog vs inline declarations).
    for name, entry_value in assistants_raw.items():
        if not isinstance(entry_value, dict):
            raise WorkflowSyntaxError(f"non-mapping assistant entry in workflow.assistants.{name}")

        scope = f"workflow.assistants.{name}"
        fields: dict[str, Any] = {}

        for key, field_value in entry_value.items():
            fields[key] = _validate_catalog_field(scope, key, field_value)

        _validate_assistant_name(name)

        catalog[name] = WorkflowAssistant(
            name=name,
            prompt=fields.get("prompt"),
            skills=fields.get("skills"),
            agent=fields.get("agent"),
            delegate=fields.get("delegate"),
            env=fields.get("env"),
        )

    return catalog


def _validate_catalog_field(scope: str, key: Any, field_value: Any) -> Any:
    """Validate one catalog-entry field value and return it (normalized), else raise.

    Args:
        scope: The dotted location of the owning entry
            (``workflow.assistants.NAME``).
        key: The catalog field key being validated.
        field_value: The raw value paired with ``key``.

    Returns:
        The validated field value (``prompt``/``agent`` str, ``skills`` a
        ``list[str]``, ``delegate`` a bool, ``env`` a ``dict[str, str]``
        carried as authored — an authored empty map is preserved, an
        explicit override that clears).

    Raises:
        WorkflowSyntaxError: If ``key`` is an unknown catalog key
            (``name``/``gate``/``when`` included), or the field value has
            the wrong type.
    """
    if key == "prompt":
        return _validate_str_field(scope, "prompt", field_value)
    elif key == "agent":
        return _validate_str_field(scope, "agent", field_value)
    elif key == "skills":
        return _validate_skills(scope, field_value)
    elif key == "delegate":
        if not isinstance(field_value, bool):
            raise WorkflowSyntaxError(f"non-bool value in {scope}.delegate")

        return field_value
    elif key == "env":
        return _validate_assistant_env(scope, field_value)
    else:
        raise WorkflowSyntaxError(f"unknown key in {scope}: {key}; valid keys: {', '.join(_ASSISTANT_CATALOG_KEYS)}")


def _validate_assistant_name(name: Any) -> None:
    """Validate an assistant name's grammar and reserved status (the name rules of 6.5).

    Args:
        name: The authored assistant name — the map key of the entry, which
            YAML may parse as a non-``str`` (an int key, for instance).

    Raises:
        WorkflowSyntaxError: If ``name`` is not a ``str`` or does not
            fullmatch ``[A-Za-z0-9._-]+``, or equals the reserved
            ``"assistant"``.
    """
    # The non-str guard comes first — a non-str key must die on the clean
    # structural message, never on a ``TypeError`` out of ``fullmatch``.
    if not isinstance(name, str) or not _ASSISTANT_NAME_PATTERN.fullmatch(name):
        raise WorkflowSyntaxError(f"invalid assistant name: {name}")

    if name == _RESERVED_ASSISTANT_NAME:
        raise WorkflowSyntaxError("assistant name is reserved")


def _build_stage_assistants(stage: Any, value: Any) -> dict[str, WorkflowAssistant] | None:
    """Validate a per-stage ``assistants`` map and build the attachment models (contract 6.7).

    Args:
        stage: The stage-name map key (used in error messages).
        value: The raw ``assistants`` value of the stage entry.

    Returns:
        The map of validated :class:`WorkflowAssistant` attachments keyed by
        assistant name, in authored order — or ``None`` when the map is
        empty (an empty map equals absence).

    Raises:
        WorkflowSyntaxError: If ``value`` is not a mapping, or an entry is
            malformed (see the entry loop below).
    """
    if not isinstance(value, dict):
        raise WorkflowSyntaxError(
            f"non-mapping assistants in workflow.stages.{stage}; author the map form keyed by assistant name"
        )

    if not value:
        # An empty map equals absence.
        return None

    attachments: dict[str, WorkflowAssistant] = {}

    for name, entry_value in value.items():
        if not isinstance(entry_value, dict):
            raise WorkflowSyntaxError(f"non-mapping assistant attachment in workflow.stages.{stage}.{name}")

        scope = f"workflow.stages.{stage}.assistants.{name}"

        # ``when`` is required on EVERY attachment, checked before the form
        # discrimination — an empty entry dies here, never as an unknown key.
        if "when" not in entry_value:
            raise WorkflowSyntaxError(f"when is required in {scope}")

        # ``gate``/``when`` are the attachment parameters. Absence
        # materializes the model defaults; an authored ``null`` is a type
        # error rejected by the validators, never an absence.
        gate = entry_value.get("gate", False)
        if not isinstance(gate, bool):
            raise WorkflowSyntaxError(f"non-bool value in {scope}.gate")

        when = _validate_when(scope, entry_value["when"])

        # The key set discriminates the two entry forms: a value within
        # ``{gate, when}`` is a reference (the declaration fields come from
        # the namespace at compile time); any further key makes it a full
        # inline declaration.
        if set(entry_value) <= {"gate", "when"}:
            _validate_assistant_name(name)

            attachments[name] = WorkflowAssistant(name=name, gate=gate, when=when)
            continue

        fields: dict[str, Any] = {}

        for key, field_value in entry_value.items():
            fields[key] = _validate_attachment_field(scope, key, field_value)

        _validate_assistant_name(name)

        attachments[name] = WorkflowAssistant(
            name=name,
            prompt=fields.get("prompt"),
            skills=fields.get("skills"),
            agent=fields.get("agent"),
            delegate=fields.get("delegate"),
            env=fields.get("env"),
            gate=gate,
            when=when,
        )

    return attachments


def _validate_attachment_field(scope: str, key: Any, field_value: Any) -> Any:
    """Validate one attachment-declaration field value and return it (normalized), else raise.

    Args:
        scope: The dotted location of the owning entry
            (``workflow.stages.STAGE.assistants.NAME``).
        key: The attachment field key being validated.
        field_value: The raw value paired with ``key``.

    Returns:
        The validated field value (``prompt``/``agent`` str, ``skills`` a
        ``list[str]``, ``delegate``/``gate`` a bool, ``when`` one of
        ``_WHEN_VALUES``, ``env`` a ``dict[str, str]`` carried as authored
        — an authored empty map is preserved, an explicit override that
        clears).

    Raises:
        WorkflowSyntaxError: If ``key`` is an unknown attachment key, or the
            field value has the wrong type.
    """
    if key == "gate":
        if not isinstance(field_value, bool):
            raise WorkflowSyntaxError(f"non-bool value in {scope}.gate")

        return field_value

    if key == "when":
        return _validate_when(scope, field_value)

    # The five shared declaration fields follow the catalog rules verbatim;
    # any key outside the seven-key attachment set is unknown here.
    if key not in _ATTACHMENT_DECLARATION_KEYS:
        valid = ", ".join(_ATTACHMENT_DECLARATION_KEYS)
        raise WorkflowSyntaxError(f"unknown key in {scope}: {key}; valid keys: {valid}")

    return _validate_catalog_field(scope, key, field_value)


def _validate_when(scope: str, field_value: Any) -> str:
    """Validate an attachment ``when`` value and return it.

    Args:
        scope: The dotted location of the owning entry
            (``workflow.stages.STAGE.assistants.NAME``).
        field_value: The raw ``when`` value to validate.

    Returns:
        The validated engagement timing (one of ``_WHEN_VALUES``).

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not a ``str``, or is a
            ``str`` other than ``"start"``/``"checkpoints"``/``"finish"``/
            ``"message"``.
    """
    if not isinstance(field_value, str):
        raise WorkflowSyntaxError(f"non-str value in {scope}.when")

    if field_value not in _WHEN_VALUES:
        raise WorkflowSyntaxError(f"when must be one of: {', '.join(_WHEN_VALUES)} in {scope}")

    return field_value


def _is_declaration(entry: WorkflowAssistant) -> bool:
    """Return whether the entry authors declaration content (the entry-form discriminator).

    Args:
        entry: The assistant entry to classify.

    Returns:
        ``True`` when any of the five declaration fields is authored —
        ``prompt``, ``skills``, ``agent``, ``delegate``, or ``env``. The
        check is PRESENCE (``is not None``), never truthiness: an authored
        ``skills: []``/``env: {}`` is a declaration while a reference
        carries ``None`` for all five fields. With the presence discipline
        every authored declaration key leaves a non-``None`` value, so this
        is exactly the parse-time key-set discrimination (keys within
        ``{gate, when}`` ⇔ reference) — the one-line declaration rule
        shared by every consuming cell.
    """
    return (
        entry.prompt is not None
        or entry.skills is not None
        or entry.agent is not None
        or entry.delegate is not None
        or entry.env is not None
    )


def _validate_assistant_namespace(
    assistants: dict[str, WorkflowAssistant],
    stages: dict[str, WorkflowStage],
) -> None:
    """Reject a declaration name repeated across the catalog and every stage (document-wide).

    Args:
        assistants: The built catalog map (name → entry).
        stages: The built per-stage map (name → ``WorkflowStage``).

    Raises:
        WorkflowSyntaxError: If a DECLARATION name occurs a second time —
            against the catalog or any inline declaration of any stage.
            References never count: a name may repeat freely across
            references.
    """
    seen: set[str] = set()

    for entry in assistants.values():
        if entry.name in seen:
            raise WorkflowSyntaxError(f"duplicate assistant name: {entry.name}")

        seen.add(entry.name)

    for stage in stages.values():
        for entry in (stage.assistants or {}).values():
            if not _is_declaration(entry):
                continue

            if entry.name in seen:
                raise WorkflowSyntaxError(f"duplicate assistant name: {entry.name}")

            seen.add(entry.name)


def _build_delegation(delegation_raw: dict[str, Any] | None) -> WorkflowDelegation | None:
    """Validate the ``delegation`` block and build the ``WorkflowDelegation`` (contract 6.6).

    Args:
        delegation_raw: The raw ``delegation`` mapping, or ``None`` when the
            block is absent.

    Returns:
        The validated :class:`WorkflowDelegation` — ``depth`` ``None`` when
        not authored (an authored ``0`` is a VALUE, never an absence) and
        ``max_tasks`` materialized to ``50`` when not authored — or ``None``
        when the block is absent. An empty block is valid and yields
        ``WorkflowDelegation(depth=None, max_tasks=50)``.

    Raises:
        WorkflowSyntaxError: If the block carries an unknown key, ``depth`` is
            not an ``int >= 0`` (``bool`` counts as non-int), or ``max_tasks``
            is not an ``int >= 1``.
    """
    if delegation_raw is None:
        return None

    depth: int | None = None
    max_tasks: int | None = None

    for key, field_value in delegation_raw.items():
        if key == "depth":
            depth = _validate_delegation_bound("depth", 0, field_value)
        elif key == "max_tasks":
            max_tasks = _validate_delegation_bound("max_tasks", 1, field_value)
        else:
            raise WorkflowSyntaxError(
                f"unknown key in workflow.delegation: {key}; valid keys: {', '.join(_DELEGATION_KEYS)}"
            )

    return WorkflowDelegation(depth=depth, max_tasks=50 if max_tasks is None else max_tasks)


def _validate_delegation_bound(key: str, minimum: int, field_value: Any) -> int:
    """Validate one ``delegation`` bound and return the confirmed ``int``.

    Args:
        key: The delegation field name (``"depth"`` or ``"max_tasks"``) —
            lands verbatim in the error messages.
        minimum: The inclusive lower bound the value must respect.
        field_value: The raw bound value to validate.

    Returns:
        The validated ``int`` (an ``int >= minimum``).

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not an ``int`` (``bool``
            counts as non-int), or is below ``minimum``.
    """
    if isinstance(field_value, bool) or not isinstance(field_value, int):
        raise WorkflowSyntaxError(f"non-int value in workflow.delegation.{key}")

    if field_value < minimum:
        raise WorkflowSyntaxError(f"{key} must be >= {minimum} in workflow.delegation")

    return field_value


def _build_repeat(repeat_raw: dict[str, Any] | None) -> WorkflowRepeat | None:
    """Validate the ``repeat`` block and build the ``WorkflowRepeat`` (contract 6.9).

    Args:
        repeat_raw: The raw ``repeat`` mapping, or ``None`` when the block is
            absent.

    Returns:
        The validated :class:`WorkflowRepeat` carrying the authored values
        only — an authored ``0`` is a VALUE, never an absence, and no default
        materializes here — or ``None`` when the block is absent or empty (an
        empty block equals absence).

    Raises:
        WorkflowSyntaxError: If the block carries an unknown key, or a value
            is not an ``int >= 0`` (``bool`` counts as non-int).
    """
    if repeat_raw is None:
        return None

    max_cycles: int | None = None
    keep_runs: int | None = None

    for key, field_value in repeat_raw.items():
        if key == "max_cycles":
            max_cycles = _validate_repeat_bound("max_cycles", field_value)
        elif key == "keep_runs":
            keep_runs = _validate_repeat_bound("keep_runs", field_value)
        else:
            raise WorkflowSyntaxError(f"unknown key in workflow.repeat: {key}; valid keys: {', '.join(_REPEAT_KEYS)}")

    if not repeat_raw:
        # An empty block equals absence.
        return None

    return WorkflowRepeat(max_cycles=max_cycles, keep_runs=keep_runs)


def _validate_repeat_bound(key: str, field_value: Any) -> int:
    """Validate one ``repeat`` bound and return the confirmed ``int``.

    Args:
        key: The repeat field name (``"max_cycles"`` or ``"keep_runs"``) —
            lands verbatim in the error messages.
        field_value: The raw bound value to validate.

    Returns:
        The validated ``int`` (an ``int >= 0``).

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not an ``int`` (``bool``
            counts as non-int), or is below zero.
    """
    if isinstance(field_value, bool) or not isinstance(field_value, int):
        raise WorkflowSyntaxError(f"non-int value in workflow.repeat.{key}")

    if field_value < 0:
        raise WorkflowSyntaxError(f"{key} must be >= 0 in workflow.repeat")

    return field_value


def _build_gates(gates_raw: dict[str, Any] | None) -> WorkflowGates | None:
    """Validate the ``gates`` settings block and build the ``WorkflowGates`` (contract 6.10).

    Args:
        gates_raw: The raw ``gates`` mapping, or ``None`` when the block is
        absent.

    Returns:
        The validated :class:`WorkflowGates` carrying the authored values
        only — an authored ``0`` is a VALUE, never an absence, and no
        default materializes here — or ``None`` when the block is absent or
        empty (an empty block equals absence).

    Raises:
        WorkflowSyntaxError: If the block carries an unknown key, a
            ``patience``/``max_iterations`` that is not an ``int >= 0``
            (``bool`` counts as non-int), or a non-bool
            ``fresh_correction``.
    """
    if gates_raw is None:
        return None

    patience: int | None = None
    max_iterations: int | None = None
    fresh_correction: bool | None = None

    for key, field_value in gates_raw.items():
        if key == "patience":
            patience = _validate_gates_bound("patience", field_value)
        elif key == "max_iterations":
            max_iterations = _validate_gates_bound("max_iterations", field_value)
        elif key == "fresh_correction":
            if not isinstance(field_value, bool):
                raise WorkflowSyntaxError("non-bool value in workflow.gates.fresh_correction")

            fresh_correction = field_value
        else:
            raise WorkflowSyntaxError(f"unknown key in workflow.gates: {key}; valid keys: {', '.join(_GATES_KEYS)}")

    if not gates_raw:
        # An empty block equals absence.
        return None

    return WorkflowGates(patience=patience, max_iterations=max_iterations, fresh_correction=fresh_correction)


def _validate_gates_bound(key: str, field_value: Any) -> int:
    """Validate one ``gates`` bound and return the confirmed ``int``.

    Args:
        key: The gates field name (``"patience"`` or ``"max_iterations"``) —
            lands verbatim in the error messages.
        field_value: The raw bound value.

    Returns:
        The validated ``int`` (an ``int >= 0``).

    Raises:
        WorkflowSyntaxError: If ``field_value`` is not an ``int`` (``bool``
            counts as non-int), or is below zero.
    """
    if isinstance(field_value, bool) or not isinstance(field_value, int):
        raise WorkflowSyntaxError(f"non-int value in workflow.gates.{key}")

    if field_value < 0:
        raise WorkflowSyntaxError(f"{key} must be >= 0 in workflow.gates")

    return field_value
