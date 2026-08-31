"""The ``parse_workflow`` routine and the ``WorkflowSyntaxError`` exception.

``parse_workflow`` is the entry point of the workflow cell: it reads a project
workflow-file, parses it as YAML, structurally validates the expected keys and
field types, builds one ``WorkflowStage`` per ``stages`` entry, builds one
``WorkflowExtendStage`` per ``extend`` entry, and returns the aggregated
``WorkflowDocument``. No content validation lives here beyond the structural
schema (the top-level key set, the per-stage key set, the extend-entry
positioning rules, field types, and the ``loop >= 1`` bound); agent-name
resolution, loop expansion, extend-stage embedding, and ``depends_on`` rewriting
are all the compiler's responsibility. The cell is intentionally declarative —
it returns instructions, never their resolution.

A workflow-file is structurally malformed when its YAML is invalid, its root is
not a mapping, it carries an unknown top-level or per-stage key, a field has the
wrong type (including a non-bool ``manual``), an extend-entry forbids
``depends_on`` / ``skip`` / ``manual`` / ``notes`` / ``reflect`` / ``memory`` /
mistypes ``before`` / ``after`` / omits both / mistypes an inline ``agent`` /
``loop`` / ``approve``, a ``loop`` is below one, its memory authoring violates
the structural schema, or it provides neither a top-level prompt, any stage
entry, any extend entry, nor the memory block. Each of those raises
``WorkflowSyntaxError`` (a ``ValueError`` subclass, mirroring the compiler
cell's ``StructuralError``) with an authored-time message. A missing or
unreadable file lets the underlying ``OSError`` propagate unchanged —
consistent with the compiler behavior.

``manual`` is accepted ONLY in the ``stages`` block (strictly a bool; an absent
key builds ``None``, NOT ``False`` — the three states stay distinguishable for
the compiler). A ``manual`` key in an extend-entry is a structural error: the
launch mode of a NEW stage is authored in its body via ``trigger`` (a full
stage-body field that passes through the extend body verbatim here — the
compiler validates its value), never via a workflow instruction. This cell
does not act on ``manual`` — it is declarative; the compiler applies the
force / cancel logic.

``notes`` is accepted ONLY in the ``stages`` block too (a map of note name →
prompt text, str→str; an empty map equals absence and builds ``None``), and is
likewise forbidden in an extend-entry — the compiler consumes it per stage name
to emit the flow-file buttons. This cell does not act on ``notes`` — it is
declarative; the runtime meaning of the buttons belongs to afm.

``memory`` is a declarative workflow-memory configuration — an optional
top-level block plus two per-stage participation instructions. The block keys
are ``method`` (``reflect``/``alignment``), ``path`` (a suffix inside the fixed
memory root), ``max_rules`` (int >= 1), ``commit`` (bool), and ``mode``
(``r``/``w``/``rw`` — alignment only, a structural error under ``reflect``);
``path`` and every ``reflect.file`` must be a valid path shape (non-empty, not
absolute, no ``..``). Under ``reflect`` a stage carries ``reflect: {file,
mode?}``; under ``alignment`` it carries ``memory: <bool>`` — an explicit
``false`` equals absence and builds ``None``. The method ↔ instruction
correspondence is enforced here (the default method is ``reflect``, so a
``memory`` instruction without an authored ``method: alignment`` block is an
error), both instructions are forbidden in an extend-entry (participation of a
new stage is authored in the ``stages`` block by its name), and a workflow
consisting of the block alone is valid. Defaults are materialized in the model,
never omitted: ``WorkflowMemory`` (method ``reflect``, ``max_rules`` 25,
``commit`` False, ``mode`` ``rw`` under alignment / ``None`` under reflect) and
``WorkflowReflect`` (``mode`` ``rw`` when the entry omits it). This cell
performs NO memory logic — it composes no paths, decides no block emission, and
resolves no stage participation; the consumer consumes the extracted values.
"""

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
    """Raised when a workflow-file is structurally malformed.

    A structural error is an authored-time defect in the workflow-file: invalid
    YAML, a non-mapping root, an unknown top-level or per-stage key, a
    wrong-typed field (including a non-bool ``manual`` or a malformed
    ``notes``), a malformed memory block or memory instruction (unknown key,
    wrong type, value outside its domain, bad path shape, a ``mode`` under the
    ``reflect`` method, or a method ↔ instruction mismatch), an extend-entry
    that
    forbids ``depends_on`` / ``skip`` / ``manual`` / ``notes`` / ``reflect`` /
    ``memory`` / mistypes
    ``before`` /
    ``after`` / an inline ``agent`` / an inline ``loop`` / an inline
    ``approve`` / omits both ``before`` and ``after``, a ``loop`` below
    one, or a workflow that provides neither a top-level prompt, any stage
    entry, any extend entry, nor the memory block. Agent-name resolution, loop
    expansion, extend-stage embedding, and ``depends_on`` rewriting are the
    compiler's
    responsibility — they never surface as structural errors here.
    """


def parse_workflow(workflow_path: Path) -> WorkflowDocument:
    """Structurally parse a workflow-file into a ``WorkflowDocument``.

    Read the file at ``workflow_path``, parse it as YAML, validate the expected
    top-level keys (``prompt``, ``stages``, ``extend``, ``memory``) and the
    per-stage key
    set (``agent``, ``prompt``, ``loop``, ``skills``, ``skip``, ``approve``,
    ``manual``, ``notes``, ``reflect``, ``memory``),
    type-check each present field (``manual`` strictly a bool; an absent key
    builds ``None``, NOT ``False``; ``notes`` a map of note name → prompt text
    whose empty form builds ``None``), validate the optional top-level
    ``memory`` block (``method`` one of ``reflect``/``alignment``, ``path`` a
    valid path shape, ``max_rules`` an ``int >= 1``, ``commit`` a bool,
    ``mode`` one of ``r``/``w``/``rw`` and forbidden under ``reflect``), the
    per-stage ``reflect`` instruction (``{file, mode?}``, ``file`` required and
    a valid path shape) and the per-stage ``memory`` instruction (strictly a
    bool; an explicit ``false`` equals absence), enforce the correspondence
    between the materialized method and the per-stage instructions (the method
    is ``reflect`` when no block is authored), validate each extend-entry's
    positioning
    (``before``/``after`` as ``list[str]``, ``depends_on`` forbidden, ``skip``
    forbidden, ``manual`` forbidden, ``notes`` forbidden, ``reflect``
    forbidden, ``memory`` forbidden, at least one of
    ``before``/``after``
    required) and any inline
    ``agent`` (str) / ``loop`` (int >= 1) / ``approve`` (one of ``auto``/
    ``plan``/``dialog``), enforce
    ``loop >= 1``, build one ``WorkflowStage`` per ``stages`` entry, one
    ``WorkflowExtendStage`` per ``extend`` entry, and one ``WorkflowMemory``
    from the ``memory`` block, and return the aggregated
    ``WorkflowDocument``. No content validation beyond the structural schema; no
    agent-name resolution, no loop expansion, no extend-stage embedding, no
    ``depends_on`` rewriting, no stage removal, and NO memory logic — no
    memory-root composition, no block-emission decision, no participation
    resolution. A ``trigger`` key in the
    ``stages`` block is an unknown-key structural error; a ``trigger`` key in
    an extend-entry body passes through verbatim (the compiler validates its
    value). This cell does not act on ``manual``, ``notes``, ``reflect``,
    ``memory``, or the memory block — they are declarative.

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

    Iterates the top-level keys once: ``prompt`` must be a str, ``stages`` must
    be a mapping, ``extend`` must be a mapping, ``memory`` must be a mapping,
    and any other key is unknown.
    Returns the validated ``prompt`` text (or ``None``), the raw ``stages``
    mapping (or ``None``), the raw ``extend`` mapping (or ``None``), and the raw
    ``memory`` mapping (or ``None``); the per-stage entries are validated by
    ``_build_stages``, the per-extend entries by ``_build_extend``, and the
    memory block by ``_build_memory``.

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

    An absent ``stages`` block (``None``) yields an empty map; a present mapping
    is validated entry by entry via ``_build_stage``. The map key is the stage
    name and is NOT validated against any pipeline here — the compiler matches
    names and silently ignores unknown ones with a warning.

    Args:
        stages_raw: The raw ``stages`` mapping, or ``None`` when absent.

    Returns:
        The map of stage name to validated ``WorkflowStage``.
    """
    if stages_raw is None:
        return {}

    return {name: _build_stage(name, value) for name, value in stages_raw.items()}


def _build_stage(name: Any, value: Any) -> WorkflowStage:
    """Validate one ``stages`` entry and build a ``WorkflowStage`` from it.

    The entry value must be a mapping. Its key set is validated against
    ``agent``, ``prompt``, ``loop``, ``skills``, ``skip``, ``approve``,
    ``manual``, ``notes``, ``reflect``, ``memory`` (unknown
    key → structural error); each present field is then type-checked, ``loop``
    must be an ``int >= 1``, ``skills`` must be a ``list[str]``, ``skip`` must be
    a ``bool``, ``approve`` must be one of ``auto``/``plan``/``dialog``,
    ``manual`` must be a ``bool``, ``reflect`` must be a ``{file, mode?}``
    mapping, and ``memory`` must be a ``bool``. Absent fields
    stay ``None`` on the built ``WorkflowStage`` (``skip`` stays ``False`` — its
    default — since absence is equivalent to ``False``; ``manual`` stays
    ``None`` — NOT ``False`` — since an absent key and an explicit
    ``manual: false`` are DIFFERENT instructions the compiler must tell apart;
    ``memory`` stays ``None`` too — an explicit ``memory: false`` is normalized
    to ``None`` at parse time because absence and an explicit false are the
    SAME state for this instruction).
    ``notes`` must be a ``dict`` of ``str``→``str``; an EMPTY map is normalized
    to ``None`` — the model carries either ``None`` or a non-empty map.

    Args:
        name: The stage-name map key (used in error messages).
        value: The raw entry value for this stage.

    Returns:
        The validated ``WorkflowStage``.

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

    Dispatches by ``key`` over the ``_STAGE_KEYS`` set, enforcing each field's
    type (``agent``/``prompt`` str, ``loop`` int >= 1, ``skills`` list[str],
    ``skip`` bool, ``approve`` one of ``auto``/``plan``/``dialog``, ``manual``
    bool, ``notes`` a str→str map, ``reflect`` a ``{file, mode?}`` mapping
    built by ``_build_reflect``, ``memory`` strictly a bool). An unknown key
    raises the unknown-key structural error with the full valid-set fragment
    (``_STAGE_KEYS`` is the single source of that fragment — ``trigger`` is a
    full stage-body field, NOT a workflow key, so it lands here as an unknown
    key). Returns the
    validated value unchanged (only ``loop`` is normalized via
    ``_validate_loop``, which already returns an ``int``; ``notes`` is
    normalized via ``_validate_notes``, which returns ``None`` for an empty
    map; ``reflect`` is normalized via ``_build_reflect``, which materializes
    the mode; ``memory`` is normalized to ``None`` when explicitly ``False``).

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

    An absent ``extend`` block (``None``) yields an empty map; a present mapping
    is validated entry by entry via ``_build_extend_stage``. The map key is the
    new stage name and is NOT validated against any pipeline here — the compiler
    embeds the stage and derives ``depends_on`` from the positioning.

    Args:
        extend_raw: The raw ``extend`` mapping, or ``None`` when absent.

    Returns:
        The map of stage name to validated ``WorkflowExtendStage``.
    """
    if extend_raw is None:
        return {}

    return {name: _build_extend_stage(name, value) for name, value in extend_raw.items()}


def _build_extend_stage(name: Any, value: Any) -> WorkflowExtendStage:
    """Validate one ``extend`` entry and build a ``WorkflowExtendStage`` from it.

    The entry value must be a mapping. ``depends_on`` is forbidden inside it
    (positioning is declared via ``before``/``after`` instead); ``skip`` is
    likewise forbidden (a new stage has no existing stage to delete, and skip is
    defined only for existing pipeline stages via the ``stages`` block);
    ``manual`` is forbidden too (the launch mode of a NEW stage is authored in
    its body via ``trigger`` — a full stage-body field that passes through
    verbatim and is validated by the compiler — never via a workflow
    instruction); ``notes`` is forbidden likewise (a declarative note-buttons
    instruction is stages-block only — the compiler consumes it per stage
    name); and the two memory-participation instructions ``reflect`` /
    ``memory`` are forbidden likewise (participation of a new stage is
    authored in the ``stages`` block by its name — the same channel the
    compiler reads);
    ``before`` and ``after`` (when present) must each be a ``list[str]``; an
    inline ``agent`` (when present) must be a ``str``; an inline ``loop`` (when
    present) must be an ``int >= 1`` (``bool`` rejected first, symmetric with
    the per-stage ``loop`` check); an inline ``approve`` (when present) must be
    one of ``auto``/``plan``/``dialog`` (validated exactly like the per-stage
    ``approve``);
    at least one of ``before``/``after`` must be present. Every other key passes
    through verbatim as the stage body. ``before``, ``after``, ``agent``,
    ``loop`` and ``approve`` are removed from the body before construction
    (``depends_on``, ``skip``, ``manual``, ``notes``, ``reflect`` and
    ``memory`` never reach it: they are rejected outright).

    The structural checks run in the CODEMANIFEST order (step 6.2):
    non-mapping → ``depends_on`` → ``skip`` → ``manual`` → ``notes`` →
    ``reflect`` → ``memory`` →
    ``before`` →
    ``after`` →
    ``agent`` → ``loop`` → ``approve`` → at-least-one-of-before/after. The
    at-least-one check runs LAST so an entry carrying BOTH a positioning defect
    (no ``before``/``after``) AND a type defect (a bad inline
    ``agent``/``loop``/``approve``) surfaces the more specific type error first,
    not the positional one.

    Args:
        name: The stage-name map key (used in error messages).
        value: The raw entry value for this extend stage.

    Returns:
        The validated ``WorkflowExtendStage``.

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

    Six keys are forbidden outright, each with its own message, checked in the
    CODEMANIFEST order before any positioning/type validation: ``depends_on``
    (positioning is declared via ``before``/``after`` instead), ``skip`` (a new
    stage has no existing stage to delete — skip is defined only for existing
    pipeline stages via the ``stages`` block), ``manual`` (the launch mode
    of a new stage is authored in its body via ``trigger``, never via a
    workflow instruction), ``notes`` (a declarative note-buttons
    instruction is stages-block only — it mirrors ``manual``: the compiler
    consumes it per stage name, and an extend-stage receives it through the
    ``stages`` block), and the two memory-participation instructions
    ``reflect`` / ``memory`` (participation of a new stage is authored in the
    ``stages`` block by its name — the same channel the compiler reads). All
    six never reach the extend body.

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

    An absent block (``None``) yields ``None`` — the document carries no memory
    configuration and the compiler's default-constructed ``WorkflowMemory()``
    supplies the authoring defaults downstream. A present mapping is validated
    key by key (unknown key → structural error listing ``_MEMORY_KEYS``;
    ``method`` / ``path`` / ``max_rules`` / ``commit`` / ``mode`` each with
    their own type and domain checks), then the mode-forbidden-under-reflect
    rule runs and the model is built with every default materialized:
    ``method`` ``"reflect"``, ``max_rules`` ``25``, ``commit`` ``False``,
    ``mode`` ``"rw"`` under alignment (the authored mode verbatim when one is
    present) and ``None`` under reflect.

    No memory-root composition happens here — ``path`` carries the authored
    suffix only; the consumer joins it with the fixed root.

    Args:
        memory_raw: The raw ``memory`` mapping, or ``None`` when absent.

    Returns:
        The validated ``WorkflowMemory``, or ``None`` when the block is absent.

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
    """Validate one ``reflect`` instruction and build the ``WorkflowReflect`` (contract 6.1.11).

    The instruction value must be a mapping whose key set is within
    ``{file, mode}`` — a non-mapping value raises the non-mapping error, an
    unknown key raises the unknown-key error listing ``_REFLECT_KEYS``.
    ``file`` is required and must be a str of a valid path shape; ``mode``
    (when present) must be a str in ``_MEMORY_MODES``. The built model carries
    the authored ``file`` verbatim and the mode materialized to ``"rw"`` when
    the entry omits it.

    The instruction's validity does NOT depend on the workflow's method here —
    the method ↔ instruction correspondence is a separate pass
    (``_validate_instruction_correspondence``) that runs after every stage is
    built, so a reflect instruction under ``alignment`` is reported by that
    pass, not this one.

    Args:
        name: The stage-name map key (used in error messages).
        value: The raw ``reflect`` entry value.

    Returns:
        The validated ``WorkflowReflect`` with the mode materialized.

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
    """Validate a per-stage ``memory`` instruction and return it (normalized).

    The participation instruction is strictly a bool; an explicit ``False`` is
    normalized to ``None`` — absence and an opting-out instruction are the
    SAME state, so the compiler's ``is True`` check never distinguishes them.
    Whether the instruction matches the workflow's method is NOT decided here
    — that correspondence is a separate pass
    (``_validate_instruction_correspondence``) running after every stage is
    built.

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
    """Reject a per-stage instruction the workflow's method does not allow (contract 6.3).

    The method is ``"reflect"`` when no block is authored — the default
    vocabulary is the reflect instruction, so a ``memory: true`` instruction
    without an explicit ``method: alignment`` block is a structural error.
    Under ``alignment`` a stage carries ``memory: true``; under ``reflect`` it
    carries a ``reflect`` instruction. Every stage is checked; the first
    mismatch raises with the stage name interpolated verbatim.

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

    A non-``str`` value is rejected first (``bool`` is not a ``str``), then any
    ``str`` other than ``"reflect"`` / ``"alignment"`` (see
    ``_MEMORY_METHODS``) is rejected. ``scope`` is the dotted location up to
    but excluding ``method`` (``"workflow.memory"``), used verbatim in both
    messages. Mirrors the non-str-then-enum shape of ``_validate_approve``.

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

    Shared by the ``memory`` block's ``mode`` key and a ``reflect``
    instruction's ``mode`` key. The two messages carry different locations:
    the type message names the exact key (``value_location``, e.g.
    ``"workflow.memory.mode"`` or ``"workflow.stages.NAME.reflect.mode"``),
    while the domain message names the mapping the key lives in
    (``domain_location`` — ``"workflow.memory"`` or
    ``"workflow.stages.NAME.reflect"``), matching the container the authored
    value was expected to complete.

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

    ``bool`` is rejected first — it is a subclass of ``int`` in Python, so
    ``max_rules: true`` must be reported as a non-int, not silently accepted —
    then non-int types, then the ``>= 1`` bound. Mirrors ``_validate_loop``,
    the established bool-first int check of this module.

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

    Shared by the ``memory`` block's ``path`` key and a ``reflect``
    instruction's ``file`` key: both name a location INSIDE the fixed memory
    root, so an empty string, an absolute path (a leading ``/``), or any ``..``
    segment is a structural error — the authored value must be a relative,
    non-escaping suffix. ``scope`` is the full dotted location of the key (e.g.
    ``"workflow.memory.path"``), interpolated verbatim into both messages; the
    invalid-shape message additionally repeats the offending value.

    The value is NOT resolved against any root here — the consumer composes
    the final path (this cell performs no memory logic).

    Args:
        scope: The dotted location of the key being validated.
        field_value: The raw path value to validate.

    Returns:
        The validated path suffix, carried verbatim.

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

    ``bool`` elements are correctly rejected: ``isinstance(True, str)`` is
    ``False``, so ``all(isinstance(x, str) for x in value)`` already yields
    ``False`` for ``[True]``. Mirrors the ``loop``-type check that rejects
    ``bool`` first in ``_build_stage``.

    Args:
        value: The candidate value to type-check.

    Returns:
        ``True`` when ``value`` is a ``list`` whose every element is a ``str``,
        else ``False``.
    """
    return isinstance(value, list) and all(isinstance(element, str) for element in value)


def _validate_loop(scope: str, field_value: Any) -> int:
    """Validate a ``loop`` field value and return the confirmed ``int``.

    Shared by the per-stage ``loop`` (``_build_stage``) and the inline extend
    ``loop`` (``_build_extend_stage``). ``bool`` is rejected first — it is a
    subclass of ``int`` in Python, so ``loop: true`` must be reported as a
    non-int, not silently accepted — then non-int types, then the ``>= 1``
    bound. ``scope`` is the dotted location up to but excluding ``loop`` (e.g.
    ``"workflow.stages.propose"``), used verbatim in both messages.

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

    Shared by the per-stage ``agent``/``prompt`` (``_validate_stage_field``) and
    the inline extend ``agent`` (``_build_extend_stage``). A non-``str`` value is
    rejected (``bool`` is not a ``str``, so it is rejected too). ``scope`` is the
    dotted location up to but excluding the field name (e.g.
    ``"workflow.stages.propose"``); ``field_name`` is appended verbatim to build
    the message location, so the same helper drives both the stages and extend
    sites.

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

    Shared by the per-stage ``approve`` (``_validate_stage_field``) and the
    inline extend ``approve`` (``_build_extend_stage``). A non-``str`` value is
    rejected first (``bool`` is not a ``str``), then any ``str`` other than the
    accepted directives — ``"auto"``, ``"plan"``, ``"dialog"`` (see
    ``_APPROVE_DIRECTIVES``) — is rejected. ``scope`` is the dotted location up
    to but excluding ``approve`` (e.g. ``"workflow.stages.deploy"``), used
    verbatim in both messages.

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

    ``notes`` is a declarative note-buttons instruction: a map of note name →
    prompt text. A non-``dict`` value is rejected first — an explicit
    ``notes: null`` included, since presence of the key forces the type check
    (the presence gating mirrors ``skip``/``manual``) — then every non-``str``
    value is rejected with the note key interpolated verbatim into the location.
    Map KEYS are deliberately not validated (the open stance mirrors the afm
    agent namespace — afm owns the runtime note grammar), so a non-str key
    flows through and lands verbatim in the error-message fragment when a
    value fails. An EMPTY map equals absence and returns ``None`` — the
    compiler's ``is not None`` check must never see an empty instruction.
    ``scope`` is the dotted location up to but excluding ``notes`` (e.g.
    ``"workflow.stages.deploy"``), used verbatim in both messages.

    Args:
        scope: The dotted location (without the trailing ``.notes``).
        field_value: The raw ``notes`` value to validate.

    Returns:
        The validated notes map, or ``None`` when the map is empty (absence).

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
