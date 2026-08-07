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
wrong type, an extend-entry forbids ``depends_on`` / mistypes ``before`` /
``after`` / omits both / mistypes an inline ``agent`` / ``loop`` / ``approve``,
a ``loop`` is below one, or it provides neither a top-level prompt, any stage
entry, nor any extend entry. Each of those raises ``WorkflowSyntaxError`` (a
``ValueError`` subclass, mirroring the compiler cell's ``StructuralError``)
with an authored-time message. A missing or unreadable file lets the underlying
``OSError`` propagate unchanged — consistent with the compiler behavior.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .workflow_document import WorkflowDocument
from .workflow_extend_stage import WorkflowExtendStage
from .workflow_stage import WorkflowStage

# Fixed keys of the top-level workflow mapping. Used for unknown-key rejection.
_TOP_LEVEL_KEYS = ("prompt", "stages", "extend")

# Fixed keys of a per-stage entry, in canonical order. Used both for unknown-key
# rejection and for documenting the accepted per-stage field set.
_STAGE_KEYS = ("agent", "prompt", "loop", "skills", "skip", "approve")

# Keys extracted out of an extend-entry's body before construction: the
# positioning keys (``before``/``after``) and the inline default overrides
# (``agent``/``loop``/``approve``). Every other key passes through verbatim as
# the stage body (``depends_on`` and ``skip`` never reach the body — they are
# rejected outright).
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
    wrong-typed field, an extend-entry that forbids ``depends_on`` / mistypes
    ``before`` / ``after`` / an inline ``agent`` / an inline ``loop`` / an
    inline ``approve`` / omits both ``before`` and ``after``, a ``loop`` below
    one, or a workflow that provides neither a top-level prompt, any stage
    entry, nor any extend entry. Agent-name resolution, loop expansion,
    extend-stage embedding, and ``depends_on`` rewriting are the compiler's
    responsibility — they never surface as structural errors here.
    """


def parse_workflow(workflow_path: Path) -> WorkflowDocument:
    """Structurally parse a workflow-file into a ``WorkflowDocument``.

    Read the file at ``workflow_path``, parse it as YAML, validate the expected
    top-level keys (``prompt``, ``stages``, ``extend``) and the per-stage key
    set (``agent``, ``prompt``, ``loop``, ``skills``, ``skip``, ``approve``),
    type-check each present field, validate each extend-entry's positioning
    (``before``/``after`` as ``list[str]``, ``depends_on`` forbidden, ``skip``
    forbidden, at least one of ``before``/``after`` required) and any inline
    ``agent`` (str) / ``loop`` (int >= 1) / ``approve`` (one of ``auto``/
    ``plan``/``dialog``), enforce
    ``loop >= 1``, build one ``WorkflowStage`` per ``stages`` entry and one
    ``WorkflowExtendStage`` per ``extend`` entry, and return the aggregated
    ``WorkflowDocument``. No content validation beyond the structural schema; no
    agent-name resolution, no loop expansion, no extend-stage embedding, no
    ``depends_on`` rewriting, no stage removal.

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
            has the wrong type (including a non-bool ``skip``), an extend-entry
            is malformed (non-mapping value, ``depends_on`` present, ``skip``
            present, ``before``/``after`` not a ``list[str]``, an inline
            ``agent`` not a str or ``loop`` not an ``int >= 1`` or ``approve``
            not one of ``auto``/``plan``/``dialog``, neither ``before`` nor
            ``after``), ``loop`` is
            below one, or the workflow provides neither a top-level prompt, any
            stage entry, nor any extend entry.
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

    prompt, stages_raw, extend_raw = _extract_top_level(loaded)

    stages = _build_stages(stages_raw)
    extend = _build_extend(extend_raw)

    if prompt is None and not stages and not extend:
        raise WorkflowSyntaxError("empty workflow — provide at least prompt, one stage, or one extend entry")

    return WorkflowDocument(prompt=prompt, stages=stages, extend=extend)


def _extract_top_level(
    loaded: dict[str, Any],
) -> tuple[str | None, dict[str, Any] | None, dict[str, Any] | None]:
    """Validate the top-level mapping and split out ``prompt``/``stages``/``extend``.

    Iterates the top-level keys once: ``prompt`` must be a str, ``stages`` must
    be a mapping, ``extend`` must be a mapping, and any other key is unknown.
    Returns the validated ``prompt`` text (or ``None``), the raw ``stages``
    mapping (or ``None``), and the raw ``extend`` mapping (or ``None``); the
    per-stage entries are validated by ``_build_stages`` and the per-extend
    entries by ``_build_extend``.

    Args:
        loaded: The YAML-parsed top-level mapping.

    Returns:
        A 3-tuple ``(prompt, stages_raw, extend_raw)`` where ``prompt`` is the
        validated top-level prompt (``None`` when absent), ``stages_raw`` is the
        raw stages mapping (``None`` when absent), and ``extend_raw`` is the raw
        extend mapping (``None`` when absent).

    Raises:
        WorkflowSyntaxError: If a top-level key is unknown, ``prompt`` is not a
            str, ``stages`` is not a mapping, or ``extend`` is not a mapping.
    """
    prompt: str | None = None
    stages_raw: dict[str, Any] | None = None
    extend_raw: dict[str, Any] | None = None

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
        else:
            raise WorkflowSyntaxError(f"unknown key in workflow: {key}; valid keys: {', '.join(_TOP_LEVEL_KEYS)}")

    return prompt, stages_raw, extend_raw


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
    ``agent``, ``prompt``, ``loop``, ``skills``, ``skip``, ``approve`` (unknown
    key → structural error); each present field is then type-checked, ``loop``
    must be an ``int >= 1``, ``skills`` must be a ``list[str]``, ``skip`` must be
    a ``bool``, and ``approve`` must be one of ``auto``/``plan``/``dialog``. Absent fields
    stay ``None`` on the built ``WorkflowStage`` (``skip`` stays ``False`` — its
    default — since absence is equivalent to ``False``).

    Args:
        name: The stage-name map key (used in error messages).
        value: The raw entry value for this stage.

    Returns:
        The validated ``WorkflowStage``.

    Raises:
        WorkflowSyntaxError: If the entry value is not a mapping, an unknown
            per-stage key is present, ``agent``/``prompt`` is not a str,
            ``loop`` is not an ``int >= 1``, ``skills`` is not a
            ``list[str]``, ``skip`` is not a ``bool``, or ``approve`` is not
            one of ``auto``/``plan``/``dialog``.
    """
    if not isinstance(value, dict):
        raise WorkflowSyntaxError(f"non-mapping stage {name} in workflow.stages")

    agent: str | None = None
    prompt: str | None = None
    loop: int | None = None
    skills: list[str] | None = None
    skip: bool = False
    approve: str | None = None

    for key, field_value in value.items():
        validated = _validate_stage_field(name, key, field_value)
        if key == "agent":
            agent = validated
        elif key == "prompt":
            prompt = validated
        elif key == "loop":
            loop = validated
        elif key == "skills":
            skills = validated
        elif key == "skip":
            skip = validated
        elif key == "approve":
            approve = validated

    return WorkflowStage(agent=agent, prompt=prompt, loop=loop, skills=skills, skip=skip, approve=approve)


def _validate_stage_field(name: Any, key: Any, field_value: Any) -> Any:
    """Validate one per-stage field value and return it (normalized), else raise.

    Dispatches by ``key`` over the ``_STAGE_KEYS`` set, enforcing each field's
    type (``agent``/``prompt`` str, ``loop`` int >= 1, ``skills`` list[str],
    ``skip`` bool, ``approve`` one of ``auto``/``plan``/``dialog``). An unknown key raises
    the unknown-key structural error with the full valid-set fragment
    (``_STAGE_KEYS`` is the single source of that fragment). Returns the
    validated value unchanged (only ``loop`` is normalized via
    ``_validate_loop``, which already returns an ``int``).

    Args:
        name: The stage-name map key (used in error messages).
        key: The per-stage field key being validated.
        field_value: The raw value paired with ``key``.

    Returns:
        The validated field value (``agent``/``prompt`` str, ``loop`` int,
        ``skills`` list[str], ``skip`` bool, or ``approve`` str equal to one of
        ``auto``/``plan``/``dialog``).

    Raises:
        WorkflowSyntaxError: If ``key`` is an unknown per-stage key, or the
            field value has the wrong type (non-str agent/prompt, non-int/<1
            loop, non-list[str] skills, non-bool skip, or an ``approve`` that
            is not a str equal to ``auto``/``plan``/``dialog``).
    """
    if key == "agent":
        return _validate_str_field(f"workflow.stages.{name}", "agent", field_value)
    elif key == "prompt":
        return _validate_str_field(f"workflow.stages.{name}", "prompt", field_value)
    elif key == "loop":
        return _validate_loop(f"workflow.stages.{name}", field_value)
    elif key == "skills":
        if not _is_list_of_str(field_value):
            raise WorkflowSyntaxError(f"non-list-of-str skills in workflow.stages.{name}")

        return field_value
    elif key == "skip":
        if not isinstance(field_value, bool):
            raise WorkflowSyntaxError(f"non-bool value in workflow.stages.{name}.skip")

        return field_value
    elif key == "approve":
        return _validate_approve(f"workflow.stages.{name}", field_value)
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
    ``before`` and ``after`` (when present) must each be a ``list[str]``; an
    inline ``agent`` (when present) must be a ``str``; an inline ``loop`` (when
    present) must be an ``int >= 1`` (``bool`` rejected first, symmetric with
    the per-stage ``loop`` check); an inline ``approve`` (when present) must be
    one of ``auto``/``plan``/``dialog`` (validated exactly like the per-stage
    ``approve``);
    at least one of ``before``/``after`` must be present. Every other key passes
    through verbatim as the stage body. ``before``, ``after``, ``agent``,
    ``loop`` and ``approve`` are removed from the body before construction
    (``depends_on`` and ``skip`` never reach it: they are rejected outright).

    The structural checks run in the CODEMANIFEST order (step 6.2):
    non-mapping → ``depends_on`` → ``skip`` → ``before`` → ``after`` →
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
            ``depends_on`` key, it contains a ``skip`` key, ``before`` is not a
            ``list[str]``, ``after`` is not a ``list[str]``, an inline
            ``agent`` is not a ``str``, an inline ``loop`` is not an
            ``int >= 1``, an inline ``approve`` is not a str equal to one of
            ``auto``/``plan``/``dialog``, or neither ``before`` nor ``after`` is present
            (checked in that order).
    """
    if not isinstance(value, dict):
        raise WorkflowSyntaxError(f"non-mapping extend entry {name} in workflow.extend")

    if "depends_on" in value:
        raise WorkflowSyntaxError(f"depends_on is forbidden in workflow.extend.{name}")

    if "skip" in value:
        raise WorkflowSyntaxError(f"skip is forbidden in workflow.extend.{name}")

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

    # At-least-one is the LAST structural check (contract step 6.2.9): a
    # multi-defect entry (no positioning AND a bad inline agent/loop/approve)
    # must surface the more specific type error raised above, not this
    # positional one.
    if before is None and after is None:
        raise WorkflowSyntaxError(f"extend entry {name} requires at least one of before/after")

    body = {key: entry_value for key, entry_value in value.items() if key not in _EXTEND_BODY_EXCLUDED}

    return WorkflowExtendStage(before=before, after=after, agent=agent, loop=loop, approve=approve, body=body)


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
