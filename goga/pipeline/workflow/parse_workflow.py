"""The ``parse_workflow`` routine and the ``WorkflowSyntaxError`` exception.

``parse_workflow`` is the entry point of the workflow cell: it reads a project
workflow-file, parses it as YAML, structurally validates the expected keys and
field types, builds one ``WorkflowStage`` per ``stages`` entry, and returns the
aggregated ``WorkflowDocument``. No content validation lives here beyond the
structural schema (the top-level key set, the per-stage key set, field types,
and the ``loop >= 1`` bound); agent-name resolution, loop expansion, and
``depends_on`` rewriting are all the compiler's responsibility. The cell is
intentionally declarative — it returns instructions, never their resolution.

A workflow-file is structurally malformed when its YAML is invalid, its root is
not a mapping, it carries an unknown top-level or per-stage key, a field has the
wrong type, a ``loop`` is below one, or it provides neither a top-level prompt
nor any stage entry. Each of those raises ``WorkflowSyntaxError`` (a
``ValueError`` subclass, mirroring the compiler cell's ``StructuralError``) with
an authored-time message. A missing or unreadable file lets the underlying
``OSError`` propagate unchanged — consistent with the compiler behavior.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .workflow_document import WorkflowDocument
from .workflow_stage import WorkflowStage

# Fixed keys of the top-level workflow mapping. Used for unknown-key rejection.
_TOP_LEVEL_KEYS = ("prompt", "stages")

# Fixed keys of a per-stage entry, in canonical order. Used both for unknown-key
# rejection and for documenting the accepted per-stage field set.
_STAGE_KEYS = ("agent", "prompt", "loop")


class WorkflowSyntaxError(ValueError):
    """Raised when a workflow-file is structurally malformed.

    A structural error is an authored-time defect in the workflow-file: invalid
    YAML, a non-mapping root, an unknown top-level or per-stage key, a
    wrong-typed field, a ``loop`` below one, or a workflow that provides neither
    a top-level prompt nor any stage entry. Agent-name resolution, loop
    expansion, and ``depends_on`` rewriting are the compiler's responsibility —
    they never surface as structural errors here.
    """


def parse_workflow(workflow_path: Path) -> WorkflowDocument:
    """Structurally parse a workflow-file into a ``WorkflowDocument``.

    Read the file at ``workflow_path``, parse it as YAML, validate the expected
    top-level keys (``prompt``, ``stages``) and the per-stage key set
    (``agent``, ``prompt``, ``loop``), type-check each present field, enforce
    ``loop >= 1``, build one ``WorkflowStage`` per entry, and return the
    aggregated ``WorkflowDocument``. No content validation beyond the structural
    schema; no agent-name resolution, no loop expansion, no ``depends_on``
    rewriting.

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
            has the wrong type, ``loop`` is below one, or the workflow provides
            neither a top-level prompt nor any stage entry.
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

    prompt, stages_raw = _extract_top_level(loaded)

    stages = _build_stages(stages_raw)

    if prompt is None and not stages:
        raise WorkflowSyntaxError("empty workflow — provide at least prompt or one stage")

    return WorkflowDocument(prompt=prompt, stages=stages)


def _extract_top_level(loaded: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    """Validate the top-level mapping and split out the ``prompt`` and ``stages`` values.

    Iterates the top-level keys once: ``prompt`` must be a str, ``stages`` must
    be a mapping, and any other key is unknown. Returns the validated ``prompt``
    text (or ``None``) and the raw ``stages`` mapping (or ``None``); the
    per-stage entries are validated by ``_build_stages``.

    Args:
        loaded: The YAML-parsed top-level mapping.

    Returns:
        A 2-tuple ``(prompt, stages_raw)`` where ``prompt`` is the validated
        top-level prompt (``None`` when absent) and ``stages_raw`` is the raw
        stages mapping (``None`` when absent).

    Raises:
        WorkflowSyntaxError: If a top-level key is unknown, ``prompt`` is not a
            str, or ``stages`` is not a mapping.
    """
    prompt: str | None = None
    stages_raw: dict[str, Any] | None = None

    for key, value in loaded.items():
        if key == "prompt":
            if not isinstance(value, str):
                raise WorkflowSyntaxError("non-str value in workflow.prompt")

            prompt = value
        elif key == "stages":
            if not isinstance(value, dict):
                raise WorkflowSyntaxError("non-mapping stages block in workflow")

            stages_raw = value
        else:
            raise WorkflowSyntaxError(
                f"unknown key in workflow: {key}; valid keys: "
                f"{', '.join(_TOP_LEVEL_KEYS)}"
            )

    return prompt, stages_raw


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
    ``agent``, ``prompt``, ``loop`` (unknown key → structural error); each
    present field is then type-checked, and ``loop`` must be an ``int >= 1``.
    Absent fields stay ``None`` on the built ``WorkflowStage``.

    Args:
        name: The stage-name map key (used in error messages).
        value: The raw entry value for this stage.

    Returns:
        The validated ``WorkflowStage``.

    Raises:
        WorkflowSyntaxError: If the entry value is not a mapping, an unknown
            per-stage key is present, ``agent``/``prompt`` is not a str, or
            ``loop`` is not an ``int >= 1``.
    """
    if not isinstance(value, dict):
        raise WorkflowSyntaxError(f"non-mapping stage {name} in workflow.stages")

    agent: str | None = None
    prompt: str | None = None
    loop: int | None = None

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
            # ``bool`` is a subclass of ``int`` in Python — reject it first so
            # ``loop: true`` is reported as a non-int, not silently accepted.
            if isinstance(field_value, bool) or not isinstance(field_value, int):
                raise WorkflowSyntaxError(f"non-int value in workflow.stages.{name}.loop")

            if field_value < 1:
                raise WorkflowSyntaxError(f"loop must be >= 1 in workflow.stages.{name}")

            loop = field_value
        else:
            raise WorkflowSyntaxError(
                f"unknown key in workflow.stages.{name}: {key}; valid keys: "
                f"{', '.join(_STAGE_KEYS)}"
            )

    return WorkflowStage(agent=agent, prompt=prompt, loop=loop)
