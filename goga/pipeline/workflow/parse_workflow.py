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
``after`` / omits both / mistypes an inline ``agent`` / ``loop``, a ``loop`` is
below one, or it provides neither a top-level prompt, any stage entry, nor any
extend entry. Each of those raises ``WorkflowSyntaxError`` (a ``ValueError``
subclass, mirroring the compiler cell's ``StructuralError``) with an
authored-time message. A missing or unreadable file lets the underlying
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
_STAGE_KEYS = ("agent", "prompt", "loop", "skills")


class WorkflowSyntaxError(ValueError):
    """Raised when a workflow-file is structurally malformed.

    A structural error is an authored-time defect in the workflow-file: invalid
    YAML, a non-mapping root, an unknown top-level or per-stage key, a
    wrong-typed field, an extend-entry that forbids ``depends_on`` / mistypes
    ``before`` / ``after`` / an inline ``agent`` / an inline ``loop`` / omits
    both ``before`` and ``after``, a ``loop`` below one, or a workflow that
    provides neither a top-level prompt, any stage entry, nor any extend entry.
    Agent-name resolution, loop expansion, extend-stage embedding, and
    ``depends_on`` rewriting are the compiler's responsibility — they never
    surface as structural errors here.
    """


def parse_workflow(workflow_path: Path) -> WorkflowDocument:
    """Structurally parse a workflow-file into a ``WorkflowDocument``.

    Read the file at ``workflow_path``, parse it as YAML, validate the expected
    top-level keys (``prompt``, ``stages``, ``extend``) and the per-stage key
    set (``agent``, ``prompt``, ``loop``, ``skills``), type-check each present
    field, validate each extend-entry's positioning (``before``/``after`` as
    ``list[str]``, ``depends_on`` forbidden, at least one of ``before``/``after``
    required) and any inline ``agent`` (str) / ``loop`` (int >= 1), enforce
    ``loop >= 1``, build one ``WorkflowStage`` per ``stages`` entry and one
    ``WorkflowExtendStage`` per ``extend`` entry, and return the aggregated
    ``WorkflowDocument``. No content validation beyond the structural schema; no
    agent-name resolution, no loop expansion, no extend-stage embedding, no
    ``depends_on`` rewriting.

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
            has the wrong type, an extend-entry is malformed (non-mapping value,
            ``depends_on`` present, ``before``/``after`` not a ``list[str]``,
            an inline ``agent`` not a str or ``loop`` not an ``int >= 1``,
            neither ``before`` nor ``after``), ``loop`` is below one, or the
            workflow provides neither a top-level prompt, any stage entry, nor
            any extend entry.
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
    ``agent``, ``prompt``, ``loop``, ``skills`` (unknown key → structural
    error); each present field is then type-checked, ``loop`` must be an
    ``int >= 1``, and ``skills`` must be a ``list[str]``. Absent fields stay
    ``None`` on the built ``WorkflowStage``.

    Args:
        name: The stage-name map key (used in error messages).
        value: The raw entry value for this stage.

    Returns:
        The validated ``WorkflowStage``.

    Raises:
        WorkflowSyntaxError: If the entry value is not a mapping, an unknown
            per-stage key is present, ``agent``/``prompt`` is not a str,
            ``loop`` is not an ``int >= 1``, or ``skills`` is not a
            ``list[str]``.
    """
    if not isinstance(value, dict):
        raise WorkflowSyntaxError(f"non-mapping stage {name} in workflow.stages")

    agent: str | None = None
    prompt: str | None = None
    loop: int | None = None
    skills: list[str] | None = None

    for key, field_value in value.items():
        if key == "agent":
            if not isinstance(field_value, str):
                raise WorkflowSyntaxError(f"non-str value in workflow.stages.{name}.agent")

            agent = field_value
        elif key == "prompt":
            if not isinstance(field_value, str):
                raise WorkflowSyntaxError(f"non-str value in workflow.stages.{name}.prompt")

            prompt = field_value
        elif key == "loop":
            loop = _validate_loop(f"workflow.stages.{name}", field_value)
        elif key == "skills":
            if not _is_list_of_str(field_value):
                raise WorkflowSyntaxError(f"non-list-of-str skills in workflow.stages.{name}")

            skills = field_value
        else:
            raise WorkflowSyntaxError(
                f"unknown key in workflow.stages.{name}: {key}; valid keys: {', '.join(_STAGE_KEYS)}"
            )

    return WorkflowStage(agent=agent, prompt=prompt, loop=loop, skills=skills)


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
    (positioning is declared via ``before``/``after`` instead); ``before`` and
    ``after`` (when present) must each be a ``list[str]``; an inline ``agent``
    (when present) must be a ``str``; an inline ``loop`` (when present) must be
    an ``int >= 1`` (``bool`` rejected first, symmetric with the per-stage
    ``loop`` check); at least one of ``before``/``after`` must be present.
    Every other key passes through verbatim as the stage body. ``before``,
    ``after``, ``agent`` and ``loop`` are removed from the body before
    construction (``depends_on`` never reaches it: it is rejected outright).

    The structural checks run in the CODEMANIFEST order (step 6b):
    non-mapping → ``depends_on`` → ``before`` → ``after`` → ``agent`` →
    ``loop`` → at-least-one-of-before/after. The at-least-one check runs LAST
    so an entry carrying BOTH a positioning defect (no ``before``/``after``)
    AND a type defect (a bad inline ``agent``/``loop``) surfaces the more
    specific type error first, not the positional one.

    Args:
        name: The stage-name map key (used in error messages).
        value: The raw entry value for this extend stage.

    Returns:
        The validated ``WorkflowExtendStage``.

    Raises:
        WorkflowSyntaxError: If the entry value is not a mapping, it contains a
            ``depends_on`` key, ``before`` is not a ``list[str]``, ``after`` is
            not a ``list[str]``, an inline ``agent`` is not a ``str``, an inline
            ``loop`` is not an ``int >= 1``, or neither ``before`` nor
            ``after`` is present (checked in that order).
    """
    if not isinstance(value, dict):
        raise WorkflowSyntaxError(f"non-mapping extend entry {name} in workflow.extend")

    if "depends_on" in value:
        raise WorkflowSyntaxError(f"depends_on is forbidden in workflow.extend.{name}")

    before = value.get("before")
    if before is not None and not _is_list_of_str(before):
        raise WorkflowSyntaxError(f"non-list-of-str before in workflow.extend.{name}")

    after = value.get("after")
    if after is not None and not _is_list_of_str(after):
        raise WorkflowSyntaxError(f"non-list-of-str after in workflow.extend.{name}")

    # Inline ``agent``/``loop`` are DEFAULT overrides (an explicit stages-block
    # entry for the same name wins per-field in the compiler). They are
    # validated per-key WITHOUT an ``is not None`` guard: an explicit ``null``
    # is a structural type error, not an absence (symmetric with the per-stage
    # ``agent``/``loop`` and the extend ``loop``). Absence is expressed by
    # omitting the key, which leaves the model field ``None``.
    agent: str | None = None
    if "agent" in value:
        agent_value = value["agent"]
        if not isinstance(agent_value, str):
            raise WorkflowSyntaxError(f"non-str value in workflow.extend.{name}.agent")

        agent = agent_value

    loop: int | None = None
    if "loop" in value:
        loop = _validate_loop(f"workflow.extend.{name}", value["loop"])

    # At-least-one is the LAST structural check (contract step 6b g): a
    # multi-defect entry (no positioning AND a bad inline agent/loop) must
    # surface the more specific type error raised above, not this positional
    # one.
    if before is None and after is None:
        raise WorkflowSyntaxError(f"extend entry {name} requires at least one of before/after")

    body = {key: entry_value for key, entry_value in value.items() if key not in ("before", "after", "agent", "loop")}

    return WorkflowExtendStage(before=before, after=after, agent=agent, loop=loop, body=body)


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
