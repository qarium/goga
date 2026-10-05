"""The ``parse_workflow`` routine and the ``WorkflowSyntaxError`` exception."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from .workflow_document import WorkflowDocument
from .workflow_extend_stage import WorkflowExtendStage
from .workflow_memory import WorkflowMemory
from .workflow_reflect import WorkflowReflect
from .workflow_stage import WorkflowStage

# Fixed keys of the top-level workflow mapping. Used for unknown-key rejection.
_TOP_LEVEL_KEYS = ("prompt", "stages", "extend", "memory")

# Fixed keys of a per-stage entry, in canonical order. Used both for unknown-key
# rejection and for documenting the accepted per-stage field set.
_STAGE_KEYS = ("agent", "prompt", "loop", "skills", "skip", "approve", "manual", "notes", "reflect", "memory")

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
# the stage body (``depends_on``, ``skip``, ``manual``, ``notes``, ``reflect``
# and ``memory`` never reach the body — they are rejected outright).
_EXTEND_BODY_EXCLUDED = ("before", "after", "agent", "loop", "approve")

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


class WorkflowSyntaxError(ValueError):
    """Raised when a workflow-file is structurally malformed (authored-time defect)."""


def parse_workflow(workflow_path: Path) -> WorkflowDocument:
    """Structurally parse a workflow-file into a ``WorkflowDocument`` — no resolution logic.

    Args:
        workflow_path: Absolute path to the workflow-file.

    Returns:
        The parsed ``WorkflowDocument`` carrying declarative instructions for
        the compiler.

    Raises:
        OSError: If ``workflow_path`` does not exist or is unreadable
            (propagated unchanged).
        WorkflowSyntaxError: If the file is invalid YAML, the root is not a
            mapping, an unknown top-level or per-stage key is present, a field
            has the wrong type (including a non-bool ``skip``, a non-bool
            ``manual``, or a ``notes`` that is non-mapping or carries a
            non-str value), the ``memory`` block or a memory instruction is
            malformed (non-mapping, unknown key, non-str ``method``/``path``/
            ``mode``/``reflect.file``, a value outside its domain, a
            ``max_rules`` that is not an ``int >= 1``, a non-bool ``commit`` or
            ``memory``, an invalid path shape, a missing ``reflect.file``, a
            ``mode`` authored under ``method: reflect``, a ``reflect``
            instruction under ``alignment``, or a ``memory`` instruction under
            ``reflect``), an extend-entry
            is malformed (non-mapping value, ``depends_on`` present, ``skip``
            present, ``manual`` present, ``notes`` present, ``reflect``
            present, ``memory`` present, ``before``/``after``
            not a
            ``list[str]``, an inline
            ``agent`` not a str or ``loop`` not an ``int >= 1`` or ``approve``
            not one of ``auto``/``plan``/``dialog``, neither ``before`` nor
            ``after``), ``loop`` is
            below one, or the workflow provides neither a top-level prompt, any
            stage entry, any extend entry, nor the memory block.
    """
    text = workflow_path.read_text()

    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError:
        # The low-level YAML scanner error is replaced with a clean structural
        # message — the parser contract does not expose the YAML internals.
        raise WorkflowSyntaxError("invalid YAML in workflow-file") from None

    if not isinstance(loaded, dict):
        raise WorkflowSyntaxError("workflow must be a mapping")

    prompt, stages_raw, extend_raw, memory_raw = _extract_top_level(loaded)

    memory = _build_memory(memory_raw)
    stages = _build_stages(stages_raw)
    extend = _build_extend(extend_raw)
    _validate_instruction_correspondence(stages, memory)

    if prompt is None and not stages and not extend and memory is None:
        raise WorkflowSyntaxError(
            "empty workflow — provide at least prompt, one stage, one extend entry, or the memory block"
        )

    return WorkflowDocument(prompt=prompt, stages=stages, extend=extend, memory=memory)


def _extract_top_level(
    loaded: dict[str, Any],
) -> tuple[str | None, dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    """Validate the top-level mapping and split out ``prompt``/``stages``/``extend``/``memory``.

    Args:
        loaded: The YAML-parsed top-level mapping.

    Returns:
        A 4-tuple ``(prompt, stages_raw, extend_raw, memory_raw)`` where
        ``prompt`` is the
        validated top-level prompt (``None`` when absent), ``stages_raw`` is the
        raw stages mapping (``None`` when absent), ``extend_raw`` is the raw
        extend mapping (``None`` when absent), and ``memory_raw`` is the raw
        memory block (``None`` when absent).

    Raises:
        WorkflowSyntaxError: If a top-level key is unknown, ``prompt`` is not a
            str, ``stages`` is not a mapping, ``extend`` is not a mapping, or
            ``memory`` is not a mapping.
    """
    prompt: str | None = None
    stages_raw: dict[str, Any] | None = None
    extend_raw: dict[str, Any] | None = None
    memory_raw: dict[str, Any] | None = None

    for key, value in loaded.items():
        if key == "prompt":
            if not isinstance(value, str):
                raise WorkflowSyntaxError("non-str value in workflow.prompt")

            prompt = value
        elif key == "stages":
            if not isinstance(value, dict):
                raise WorkflowSyntaxError("non-mapping stages block in workflow")

            stages_raw = value
        elif key == "extend":
            if not isinstance(value, dict):
                raise WorkflowSyntaxError("non-mapping extend block in workflow")

            extend_raw = value
        elif key == "memory":
            if not isinstance(value, dict):
                raise WorkflowSyntaxError("non-mapping memory block in workflow")

            memory_raw = value
        else:
            raise WorkflowSyntaxError(f"unknown key in workflow: {key}; valid keys: {', '.join(_TOP_LEVEL_KEYS)}")

    return prompt, stages_raw, extend_raw, memory_raw


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
        ``skip`` (``False``); an explicit ``memory: false`` and an empty
        ``notes`` map normalize to ``None``.

    Raises:
        WorkflowSyntaxError: If the entry value is not a mapping, an unknown
            per-stage key is present, ``agent``/``prompt`` is not a str,
            ``loop`` is not an ``int >= 1``, ``skills`` is not a
            ``list[str]``, ``skip`` is not a ``bool``, ``approve`` is not
            one of ``auto``/``plan``/``dialog``, ``manual`` is not a
            ``bool``, ``notes`` is not a ``dict`` of ``str``→``str``,
            ``reflect`` is malformed (see ``_build_reflect``), or ``memory``
            is not a ``bool``.
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
        prompt=fields.get("prompt"),
        loop=fields.get("loop"),
        skills=fields.get("skills"),
        skip=fields.get("skip", False),
        approve=fields.get("approve"),
        manual=fields.get("manual"),
        notes=fields.get("notes"),
        reflect=fields.get("reflect"),
        memory=fields.get("memory"),
    )


def _validate_stage_field(name: Any, key: Any, field_value: Any) -> Any:
    """Validate one per-stage field value and return it (normalized), else raise.

    Args:
        name: The stage-name map key (used in error messages).
        key: The per-stage field key being validated.
        field_value: The raw value paired with ``key``.

    Returns:
        The validated field value (``agent``/``prompt`` str, ``loop`` int,
        ``skills`` list[str], ``skip`` bool, ``approve`` str equal to one of
        ``auto``/``plan``/``dialog``, ``manual`` bool, ``notes`` a non-empty
        ``dict[str, str]`` — ``None`` when the map is empty —, ``reflect`` a
        ``WorkflowReflect``, or ``memory`` a bool — ``None`` when explicitly
        ``False``).

    Raises:
        WorkflowSyntaxError: If ``key`` is an unknown per-stage key, or the
            field value has the wrong type (non-str agent/prompt, non-int/<1
            loop, non-list[str] skills, non-bool skip, an ``approve`` that
            is not a str equal to ``auto``/``plan``/``dialog``, a non-bool
            ``manual``, ``notes`` that is non-mapping or carries a non-str
            value, a malformed ``reflect`` instruction, or a non-bool
            ``memory``).
    """
    if key in ("agent", "prompt"):
        return _validate_str_field(f"workflow.stages.{name}", key, field_value)
    elif key == "loop":
        return _validate_loop(f"workflow.stages.{name}", field_value)
    elif key == "skills":
        if not _is_list_of_str(field_value):
            raise WorkflowSyntaxError(f"non-list-of-str skills in workflow.stages.{name}")

        return field_value
    elif key in ("skip", "manual"):
        # Both are strictly-bool flags sharing the same message shape; the
        # field name lands verbatim in the location fragment.
        if not isinstance(field_value, bool):
            raise WorkflowSyntaxError(f"non-bool value in workflow.stages.{name}.{key}")

        return field_value
    elif key in ("approve", "notes"):
        # Two scoped single-value validators sharing the stage as their
        # location; each validator owns its own message shape.
        scope = f"workflow.stages.{name}"
        validator = _validate_approve if key == "approve" else _validate_notes
        return validator(scope, field_value)
    elif key in ("reflect", "memory"):
        # Two scoped single-value validators sharing the stage as their
        # location; each validator owns its own message shape.
        validator = _build_reflect if key == "reflect" else _validate_memory_instruction
        return validator(name, field_value)
    else:
        raise WorkflowSyntaxError(f"unknown key in workflow.stages.{name}: {key}; valid keys: {', '.join(_STAGE_KEYS)}")


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
            ``reflect`` key, it contains a ``memory`` key, ``before`` is not a
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
    """Reject the keys an extend-entry must never carry (contract 6.2.2 - 6.2.7).

    Args:
        name: The stage-name map key (used in error messages).
        value: The raw entry value for this extend stage.

    Raises:
        WorkflowSyntaxError: If the entry carries ``depends_on``, ``skip``,
            ``manual``, ``notes``, ``reflect``, or ``memory`` (checked in that
            order).
    """
    for forbidden_key in ("depends_on", "skip", "manual", "notes", "reflect", "memory"):
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
