"""The ``compile_flow`` entry point — read a pipeline-file, compile, write a flow-file.

``compile_flow`` is the entry point of the compiler cell: it reads a goga DSL
pipeline-file (phases-list or stages-map), parses it via ``parse_dsl``, applies
the per-format ``depends_on`` rules (PHASES: position-derived; STAGES:
pass-through), reorders each step body into canonical key order via the internal
``_canonical_fields`` helper, builds a ``FlowDocument``, serializes it via
``serialize_flow``, and writes the result to ``flow_path``. It performs no
environment-variable reads and no subprocess calls — the caller supplies both
paths explicitly.

When the caller passes a non-``None`` ``workflow`` (a ``WorkflowDocument``), the
parsed body is reconstructed BEFORE the ``FlowStage`` assembly: per-stage
agent/prompt overrides are injected into the step bodies, looped stages are
expanded into N chained copies (``NAME-1``..``NAME-N``), and external
``depends_on`` references are rewritten to the LAST expanded id. The
reconstruction operates on a deep copy of the parsed steps — the
``PipelineDocument`` returned to the consumer always carries the ORIGINAL parsed
body, never the reconstructed one. Unknown workflow stage names (names absent
from the pipeline) are skipped with a ``WARNING`` log line.

I/O exceptions and structural errors from ``parse_dsl`` propagate unchanged. An
empty body raises ``StructuralError("empty body")`` here — not in ``parse_dsl``,
which lets empty bodies through for ``compile_flow`` to reject.
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

from goga.pipeline.workflow import WorkflowDocument

from .body_format import BodyFormat
from .flow_document import FlowDocument
from .flow_stage import FlowStage
from .parse_dsl import StructuralError, parse_dsl
from .phase_step import PhaseStep
from .phases_body import PhasesBody
from .pipeline_document import PipelineDocument
from .serialize_flow import serialize_flow
from .stage_step import StageStep
from .stages_body import StagesBody

logger = logging.getLogger(__name__)

# Canonical key order for the output stage fields. ``serialize_flow`` emits
# ``FlowStage.fields`` verbatim, so canonical order must be established here.
# ``command`` and ``description`` are populated by per-stage workflow overrides
# (workflow branch); when absent they are simply skipped by the loop below.
_CANONICAL_KEY_ORDER = ["interactive", "command", "prompt", "description", "agents", "skills"]

# In-container wrapper path template consumed by afm 0.4.15 as the per-stage
# ``command:`` override. Composed directly from the ``WorkflowStage`` agent name
# — the cell does NOT call any host-side wrapper resolver.
_WRAPPER_PATH_TEMPLATE = "/home/goga/bin/{agent}-as-claude.sh"

# Loop count at and above which a stage is expanded into multiple copies.
# ``>= _LOOP_EXPANSION_THRESHOLD`` triggers expansion (and an external
# depends_on rewrite to the LAST expanded id); a count of ``1`` is a no-op.
_LOOP_EXPANSION_THRESHOLD = 2


def _canonical_fields(body: dict[str, Any]) -> dict[str, Any]:
    """Reorder ``body`` into canonical key order, deep-copying each value.

    Known keys (``interactive``, ``command``, ``prompt``, ``description``,
    ``agents``, ``skills``) are emitted first in that fixed order; any remaining
    keys are appended alphabetically. Each value is deep-copied so the returned
    dict shares no structure with the parsed body — isolating the compiler's
    output from caller mutation.

    Args:
        body: The step body dict produced by ``parse_dsl``.

    Returns:
        A new dict in canonical key order with deep-copied values.
    """
    ordered: dict[str, Any] = {}
    for key in _CANONICAL_KEY_ORDER:
        if key in body:
            ordered[key] = copy.deepcopy(body[key])
    extras = sorted(k for k in body if k not in _CANONICAL_KEY_ORDER)
    for key in extras:
        ordered[key] = copy.deepcopy(body[key])
    return ordered


def _apply_per_stage_overrides(
    steps: list[PhaseStep | StageStep],
    workflow: WorkflowDocument,
) -> None:
    """Inject per-stage agent/prompt overrides into the matching step bodies.

    For each ``(name, WorkflowStage)`` in ``workflow.stages``: the step with a
    matching name/id is found in ``steps`` (mutated in place); when no step
    matches, a ``WARNING`` is logged and the entry is skipped (a workflow may
    intentionally cover multiple pipelines). When found, a non-``None`` ``agent``
    composes the in-container wrapper path into the step body's ``command`` slot,
    and a non-``None`` ``prompt`` copies its text into the step body's
    ``description`` slot. Operates on the supplied (already deep-copied) working
    sequence so the ORIGINAL parsed body stays untouched.

    Args:
        steps: The working (deep-copied) step sequence to mutate in place.
        workflow: The declarative workflow instructions.
    """
    steps_by_name = {step.name: step for step in steps}
    for name, stage in workflow.stages.items():
        step = steps_by_name.get(name)
        if step is None:
            logger.warning(
                "compile_flow: workflow stage %r not found in pipeline; skipping", name,
            )
            continue
        if stage.agent is not None:
            step.body["command"] = _WRAPPER_PATH_TEMPLATE.format(agent=stage.agent)
        if stage.prompt is not None:
            step.body["description"] = stage.prompt


def _make_expanded_copy(
    step: PhaseStep | StageStep,
    new_id: str,
    index: int,
    fmt: BodyFormat,
) -> PhaseStep | StageStep:
    """Build one loop-expanded copy of ``step`` carrying the id ``new_id``.

    PHASES copies carry no ``depends_on`` (position derives it later); STAGES
    copies carry the original step's external ``depends_on`` on the FIRST copy
    (deep-copied so the rewrite pass can mutate it freely) and an internal chain
    reference to the previous copy (``NAME-(index-1)``) on every subsequent copy.
    The body is deep-copied so copies never alias one another or the base step.

    Args:
        step: The (override-applied) base step being expanded.
        new_id: The id for this copy (``NAME-<index>``).
        index: 1-based position within the expanded group.
        fmt: The body format — selects ``PhaseStep`` vs ``StageStep``.

    Returns:
        A new step instance for the expanded copy.
    """
    body = copy.deepcopy(step.body)
    if fmt is BodyFormat.PHASES:
        return PhaseStep(name=new_id, description=step.description, body=body)
    # STAGES: first copy inherits the original external depends_on (rewritten in
    # 5c); later copies chain to the previous copy by id.
    if index == 1:
        assert isinstance(step, StageStep)
        depends_on = copy.deepcopy(step.depends_on)
    else:
        depends_on = [f"{step.name}-{index - 1}"]
    return StageStep(name=new_id, description=step.description, depends_on=depends_on, body=body)


def _expand_loops(
    steps: list[PhaseStep | StageStep],
    workflow: WorkflowDocument,
    fmt: BodyFormat,
) -> tuple[list[PhaseStep | StageStep], dict[str, list[str]]]:
    """Expand looped stages into N chained copies, preserving source order.

    For each step in source order: ``loop_count`` is the workflow's ``loop`` for
    the step's name when set, otherwise ``1``. A ``loop_count`` of ``1`` appends
    the step unchanged and records the base-name → ``[base-name]``. A
    ``loop_count >= 2`` appends ``N`` copies ``NAME-1``..``NAME-N`` (built via
    ``_make_expanded_copy``) and records the base-name → ``[NAME-1, ..., NAME-N]``.

    Args:
        steps: The override-applied working step sequence.
        workflow: The declarative workflow instructions (source of loop counts).
        fmt: The body format — selects the expanded step type.

    Returns:
        The new ordered step list and the base-name → produced-ids map.
    """
    expanded: list[PhaseStep | StageStep] = []
    expanded_ids: dict[str, list[str]] = {}
    for step in steps:
        loop_count = 1
        wf_stage = workflow.stages.get(step.name)
        if wf_stage is not None and wf_stage.loop is not None:
            loop_count = wf_stage.loop
        if loop_count == 1:
            expanded.append(step)
            expanded_ids[step.name] = [step.name]
            continue
        ids = [f"{step.name}-{i}" for i in range(1, loop_count + 1)]
        for index, new_id in enumerate(ids, start=1):
            expanded.append(_make_expanded_copy(step, new_id, index, fmt))
        expanded_ids[step.name] = ids
    return expanded, expanded_ids


def _rewrite_external_depends_on(
    steps: list[StageStep],
    expanded_ids: dict[str, list[str]],
) -> None:
    """Rewrite external depends_on refs to the LAST expanded id (STAGES only).

    For each ``StageStep`` with a non-``None`` ``depends_on``: a reference to a
    base-name whose loop count was ``>= 2`` is replaced with the LAST id from
    that base-name's expanded-ids list; a reference to a base-name with loop
    count ``1`` (whose single id equals the base-name) is kept as-is; an
    unmatched reference is kept as-is for afm to surface as a dangling ref.

    Args:
        steps: The loop-expanded STAGES sequence to rewrite in place.
        expanded_ids: The base-name → produced-ids map from ``_expand_loops``.
    """
    for step in steps:
        if step.depends_on is None:
            continue
        rewritten: list[str] = []
        for ref in step.depends_on:
            produced = expanded_ids.get(ref)
            if produced is not None and len(produced) >= _LOOP_EXPANSION_THRESHOLD:
                rewritten.append(produced[-1])
            else:
                rewritten.append(ref)
        step.depends_on = rewritten


def _reconstruct_body(
    fmt: BodyFormat,
    body: PhasesBody | StagesBody,
    workflow: WorkflowDocument,
) -> list[PhaseStep | StageStep]:
    """Apply the workflow reconstruction branch, returning a NEW step sequence.

    Deep-copies the parsed steps first so the ORIGINAL body (returned later via
    ``PipelineDocument``) is never mutated, then runs the four sub-steps from the
    CODEMANIFEST algorithm: (5a) per-stage overrides; (5b) loop-expansion with
    the expanded-ids map; (5c) external depends_on rewrite (STAGES only); the
    result (5d) is the reconstructed step list consumed for ``FlowStage``
    assembly.

    Args:
        fmt: The body format — PHASES or STAGES.
        body: The ORIGINAL parsed body (never mutated here).
        workflow: The declarative workflow instructions.

    Returns:
        The reconstructed step sequence (PHASES or STAGES steps).
    """
    steps: list[PhaseStep | StageStep] = [copy.deepcopy(step) for step in body.steps]
    _apply_per_stage_overrides(steps, workflow)
    expanded, expanded_ids = _expand_loops(steps, workflow, fmt)
    if fmt is BodyFormat.STAGES:
        _rewrite_external_depends_on(expanded, expanded_ids)
    return expanded


def compile_flow(
    pipeline_path: Path,
    flow_path: Path,
    workflow: WorkflowDocument | None = None,
) -> tuple[PipelineDocument, FlowDocument]:
    """Compile a goga DSL pipeline-file into an afm flow-file and return both documents.

    Reads ``pipeline_path``, parses it with ``parse_dsl``, rejects an empty body
    with ``StructuralError("empty body")``, then builds a ``FlowDocument`` whose
    stages carry canonical-key-order ``fields`` and per-format ``depends_on``
    (position-derived for PHASES — the first step gets none, each subsequent step
    depends on its predecessor; pass-through for STAGES). The document is
    serialized via ``serialize_flow`` and written to ``flow_path`` (overwriting if
    it exists) as a side effect. I/O errors and structural errors from ``parse_dsl``
    propagate unchanged; ``compile_flow`` does not read ``AFM_DIR``.

    When ``workflow`` is not ``None``, the parsed body is reconstructed
    (per-stage overrides, loop-expansion, external depends_on rewrite) on a deep
    copy BEFORE the ``FlowStage`` assembly; the top-level ``prompt`` of the
    workflow is emitted as the first key of the flow-file. When ``workflow`` is
    ``None`` no workflow is applied — the output carries no top-level prompt and
    no per-stage overrides.

    In addition to the flow-file, it builds a ``PipelineDocument`` aggregating the
    parsed ``header`` (including any inline ``agents`` overrides), ``format``, and
    the ORIGINAL ``body`` (never the reconstructed one) so consumers can obtain
    the parsed representation without re-invoking ``parse_dsl``. ``FlowDocument``
    never carries ``agents`` — it is a goga-side artifact of the compiler, not
    part of the compiled afm flow-file.

    Args:
        pipeline_path: Absolute path to the input goga DSL pipeline-file. The file
            must be readable and contain a ``---`` separator line.
        flow_path: Absolute path to the output afm flow-file. The parent directory
            must already exist; it is not created here.
        workflow: Optional ``WorkflowDocument`` carrying declarative instructions
            for extending the pipeline (top-level prompt, per-stage
            agent/prompt/loop overrides). When ``None`` no workflow is applied.

    Returns:
        A ``(PipelineDocument, FlowDocument)`` documents tuple. The
        ``PipelineDocument`` carries the parsed header (with ``header.agents``),
        format, and the ORIGINAL body; the ``FlowDocument`` carries the name,
        description, optional top-level prompt, and compiled stages (without
        ``agents``).

    Raises:
        StructuralError: On a structural defect in the DSL (propagated from
            ``parse_dsl``) or on an empty body.
        FileNotFoundError: If ``pipeline_path`` does not exist or ``flow_path``'s
            parent is missing (propagated).
        PermissionError: If ``pipeline_path`` is unreadable (propagated).
    """
    logger.info("compile_flow: %s → %s", pipeline_path, flow_path)

    text = pipeline_path.read_text()
    header, fmt, body = parse_dsl(text)

    if len(body.steps) == 0:
        raise StructuralError("empty body")

    # The step sequence consumed for FlowStage assembly. When a workflow is
    # applied, this is a reconstructed (deep-copied + overridden + expanded)
    # sequence; the ORIGINAL `body` is preserved for PipelineDocument below.
    reconstructed = (
        _reconstruct_body(fmt, body, workflow) if workflow is not None else list(body.steps)
    )

    stages: list[FlowStage] = []
    if fmt is BodyFormat.PHASES:
        for i, step in enumerate(reconstructed):
            depends_on = [reconstructed[i - 1].name] if i > 0 else None
            fields = _canonical_fields(step.body)
            stages.append(
                FlowStage(
                    id=step.name,
                    name=step.description,
                    depends_on=depends_on,
                    fields=fields,
                ),
            )
    elif fmt is BodyFormat.STAGES:
        for step in reconstructed:
            fields = _canonical_fields(step.body)
            stages.append(
                FlowStage(
                    id=step.name,
                    name=step.description,
                    depends_on=step.depends_on,
                    fields=fields,
                ),
            )

    flow_prompt = workflow.prompt if workflow is not None else None
    doc = FlowDocument(prompt=flow_prompt, name=header.name, description=header.description, stages=stages)
    pipeline_doc = PipelineDocument(header=header, format=fmt, body=body)
    text_out = serialize_flow(doc)
    flow_path.write_text(text_out)
    return (pipeline_doc, doc)
