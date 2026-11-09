"""The ``apply_gate_env_wrappers`` routine — the per-step sh closures delivering gate env layers."""

from __future__ import annotations

import logging
import re
import shlex
from pathlib import Path

from ..agents import resolve_wrapper_path
from .compiler import FlowStage, FlowVerify, FlowVerifyStep
from .stage_env_wrappers import (
    _LEGAL_ENV_NAME_PATTERN,
    _find_stage_block,
    _wrapper_file_name,
    _write_owner_only,
)
from .workflow import WorkflowDocument, WorkflowGateStep, WorkflowStage

logger = logging.getLogger(__name__)

# The container-local base directory of the generated gate closures — never
# under /workspace or the project directory. A module constant so the tests
# (and only they) can relocate it.
_GATE_WRAPPER_BASE = Path("/tmp/goga-gate-env")

# The serialized verify-step field line at an exact indent — the patch target.
# ``run``/``command`` is the only field the rewrite touches; the authored
# ``name``/``timeout``/``prompt`` lines stay byte-identical.
_STEP_FIELD_PATTERN = re.compile(r"^( +)(run|command):")

# The serialized indentation grammar of the verify section: the stage-field
# indent (``verify:`` itself and a list-form step entry), the container-form
# nesting indents (``steps:`` and its entries, then the settings), and the
# depth a block-literal continuation line exceeds its field by.
_STAGE_FIELD_INDENT = 2
_CONTAINER_INDENT = 4


def _line_indent(line: str) -> int:
    """Measure one serialized line's leading-space indent.

    Args:
        line: The serialized flow-file line (``splitlines(keepends=True)`` form).

    Returns:
        The number of leading spaces.
    """
    return len(line) - len(line.lstrip(" "))


def _select_gate_claims(
    stages: list[FlowStage],
    workflow: WorkflowDocument,
) -> dict[str, WorkflowStage]:
    """Map every gate-env-claiming stage id to its declaring workflow stage.

    Args:
        stages: The compiled flow stages — the claim targets.
        workflow: The effective workflow document (its stages map carries the
            gate instructions).

    Returns:
        The stage-id → workflow stage map. A workflow stage claims a compiled
        stage when its gates list carries at least one non-None step env map;
        exact id matches claim first (across every workflow name — exact beats
        suffix), the remaining ids are then claimed by the ``<name>-<digits>``
        loop-expansion suffix of a workflow stage name — the same resolution
        :func:`apply_stage_env_wrappers` applies to the per-stage env.
    """

    def _claims_gates(wstage: WorkflowStage) -> bool:
        return wstage.gates is not None and any(step.env is not None for step in wstage.gates)

    env_entries = [(name, stage) for name, stage in workflow.stages.items() if _claims_gates(stage)]
    claims: dict[str, WorkflowStage] = {}

    for name, wstage in env_entries:
        for stage in stages:
            if stage.id == name:
                claims[stage.id] = wstage

    for name, wstage in env_entries:
        suffix_pattern = re.compile(rf"{re.escape(name)}-\d+")

        for stage in stages:
            if stage.id not in claims and suffix_pattern.fullmatch(stage.id):
                claims[stage.id] = wstage

    return claims


def _render_step_closure(script: str | None, agent: str | None, env: dict[str, str]) -> str:
    """Render one gate step's sh closure: export the env, then carry the payload.

    Args:
        script: The authored shell command of a script step, or ``None`` on an
            agent step.
        agent: The authored agent name of an AI-review step, or ``None`` on a
            script step.
        env: The step's authored env map — exported VERBATIM (no engine-key
            dropping; a gate layer sits above all global layers).

    Returns:
        The script text: the shebang, one ``export`` line per entry (values
        shell-quoted, authored order), then the payload — the authored script
        lines as-is on a script step (the same shell, working directory, and
        exit status the engine would give the authored ``run`` value), or the
        exec of the agent's in-container wrapper forwarding ``"$@"`` on an AI
        step (the stage-env closure shape).
    """
    exports = "".join(f"export {key}={shlex.quote(value)}\n" for key, value in env.items())

    if script is not None:
        payload = script if script.endswith("\n") else script + "\n"

        return f"#!/bin/sh\n{exports}{payload}"

    return f'#!/bin/sh\n{exports}exec {shlex.quote(resolve_wrapper_path(agent))} "$@"\n'


def _patched_stage(stage: FlowStage, wrappers: dict[int, Path], authored: list[WorkflowGateStep]) -> FlowStage:
    """Build one claimed stage's replacement with its env steps rewritten.

    Args:
        stage: The compiled stage — read-only input.
        wrappers: The step-index → wrapper path map of this stage's claimed
            steps.
        authored: The declaring workflow stage's gates list — the authored
            step kinds decide which compiled field each wrapper replaces
            (``run`` for a script step, ``command`` for an agent step).

    Returns:
        A new ``FlowStage`` carrying a fresh fields dict with a rebuilt
        ``verify`` gate: each claimed step is a new ``FlowVerifyStep`` with
        its ``run`` (a script step) or ``command`` (an agent step) pointing
        at the wrapper; every other field value is carried verbatim. The
        input object and its field values are never mutated.
    """
    verify = stage.fields["verify"]
    steps: list[FlowVerifyStep] = []

    for index, step in enumerate(verify.steps):
        if index not in wrappers:
            steps.append(step)
            continue

        if authored[index].script is not None:
            steps.append(
                FlowVerifyStep(name=step.name, run=str(wrappers[index]), timeout=step.timeout, prompt=step.prompt)
            )
        else:
            steps.append(
                FlowVerifyStep(
                    name=step.name,
                    command=str(wrappers[index]),
                    timeout=step.timeout,
                    prompt=step.prompt,
                )
            )

    gate = FlowVerify(
        steps=steps,
        max_failures=verify.max_failures,
        review_patience=verify.review_patience,
        fresh_correction=verify.fresh_correction,
    )
    fields = dict(stage.fields)
    fields["verify"] = gate

    return FlowStage(id=stage.id, name=stage.name, depends_on=stage.depends_on, fields=fields)


def _verify_entry_positions(body: list[str], verify_at: int) -> list[int]:
    """Collect the verify section's step-entry offsets inside one stage block body.

    Args:
        body: The stage block's member lines (``splitlines(keepends=True)``
            form, without the ``- id:`` header).
        verify_at: The offset of the ``  verify:`` line inside ``body``.

    Returns:
        The offsets of the step-entry header lines (``- name: …``), in
        serialized order — the authored order the compiler preserved.
    """
    entry_positions: list[int] = []

    for offset, line in enumerate(body[verify_at + 1 :], verify_at + 1):
        if not line.strip():
            # Truly empty lines occur only INSIDE multi-line scalars — a
            # paragraph break of a step value continues the section.
            continue

        if not line.startswith(" "):
            break

        indent = _line_indent(line)

        if indent == _STAGE_FIELD_INDENT and not line.startswith("  - "):
            # A stage field (e.g. ``depends_on:``) ends the verify section —
            # its own dash items must never count as verify steps.
            break

        if indent in (_STAGE_FIELD_INDENT, _CONTAINER_INDENT) and line.lstrip(" ").startswith("- "):
            entry_positions.append(offset)

    return entry_positions


def _step_field_position(body: list[str], entry_at: int, entry_indent: int) -> int | None:
    """Locate one step entry's ``run``/``command`` field line.

    Args:
        body: The stage block's member lines.
        entry_at: The offset of the step-entry header line.
        entry_indent: The entry header's indent.

    Returns:
        The offset of the entry's ``run``/``command`` field line, or ``None``
        when the entry carries none.
    """
    cursor = entry_at + 1

    while cursor < len(body):
        line = body[cursor]
        match = _STEP_FIELD_PATTERN.match(line)

        # The indent must be EXACTLY the field indent — a block-literal
        # continuation line (a prompt line reading "run: …") sits deeper and
        # must never capture the rewrite.
        if match is not None and len(match.group(1)) == entry_indent + _STAGE_FIELD_INDENT:
            return cursor

        if line.lstrip(" ").startswith("- ") or not line.startswith(" "):
            break

        cursor += 1

    return None


def _step_value_end(body: list[str], field_at: int, field_indent: int) -> int:
    """Measure the exclusive end of the field's serialized value.

    Args:
        body: The stage block's member lines.
        field_at: The offset of the ``run``/``command`` field line.
        field_indent: The field line's indent.

    Returns:
        The offset one past the field's last value line — the field line plus
        any block-literal continuation lines (deeper than the field indent; a
        blank line belongs to the literal only when a still-deeper line
        follows it — a paragraph break inside the value). A single-line value
        ends at ``field_at + 1``.
    """
    value_end = field_at + 1

    while value_end < len(body):
        line = body[value_end]

        if not line.strip():
            lookahead = next((j for j in range(value_end + 1, len(body)) if body[j].strip()), None)

            if lookahead is None or _line_indent(body[lookahead]) <= field_indent:
                break

            value_end += 1
            continue

        if not line.startswith(" ") or _line_indent(line) <= field_indent:
            break

        value_end += 1

    return value_end


def _patch_verify_step(text: str, stage_id: str, index: int, wrapper: str) -> str:
    """Rewrite exactly one verify step's ``run``/``command`` field in the serialized text.

    Args:
        text: The flow-file text.
        stage_id: The claimed stage id — locates the stage block.
        index: The step's position in the stage's verify list (the authored
            order the compiler preserved).
        wrapper: The absolute wrapper path — the new field value.

    Returns:
        The patched text. The step's ``run``/``command`` line is rewritten in
        place (a block-literal old value — a multi-line authored script — is
        consumed with its continuation lines); every other byte stays
        untouched (a targeted text patch, never a YAML round-trip). Both
        emission forms are handled: the list form nests the step entries at
        two spaces under ``verify:``, the container form at four under
        ``steps:`` — the entry indent is read from the serialized text, never
        assumed.

    Raises:
        ValueError: When the stage block carries no ``verify:`` section or
        fewer than ``index + 1`` step entries (the flow-file and the compiled
        gate disagree — an internal invariant breach).
    """
    lines = text.splitlines(keepends=True)
    start, end = _find_stage_block(lines, stage_id)
    body = lines[start + 1 : end]

    try:
        verify_at = body.index("  verify:\n")
    except ValueError:
        raise ValueError(f"stage {stage_id!r} carries no verify gate in the flow-file") from None

    entry_positions = _verify_entry_positions(body, verify_at)

    if index >= len(entry_positions):
        raise ValueError(f"stage {stage_id!r} carries fewer than {index + 1} verify steps in the flow-file")

    entry_at = entry_positions[index]
    entry_indent = _line_indent(body[entry_at])
    field_indent = entry_indent + _STAGE_FIELD_INDENT

    field_at = _step_field_position(body, entry_at, entry_indent)

    if field_at is None:
        raise ValueError(f"verify step {index} of stage {stage_id!r} carries no run/command field in the flow-file")

    key = _STEP_FIELD_PATTERN.match(body[field_at]).group(2)
    value_end = _step_value_end(body, field_at, field_indent)

    body[field_at:value_end] = [" " * field_indent + f"{key}: {wrapper}\n"]

    return "".join(lines[: start + 1] + body + lines[end:])


def _validate_env_names(claims: dict[str, WorkflowStage]) -> None:
    """Validate every claimed step's env keys as legal environment variable names.

    Args:
        claims: The stage-id → workflow stage map of the delivery.

    Raises:
        ValueError: When a claimed step's env key is not a legal environment
            variable name (POSIX shape) — naming the stage, the step, and the
            key. Raised before any wrapper file is written: a key with a
            shell metacharacter would inject into (or break) the generated
            export line, so no partial wrapper set can reach a gate launch.
    """
    for stage_id, wstage in claims.items():
        for step in wstage.gates:
            if step.env is None:
                continue

            for key in step.env:
                if _LEGAL_ENV_NAME_PATTERN.fullmatch(key) is None:
                    raise ValueError(
                        f"invalid environment variable name in the {stage_id} stage gate {step.name} env: {key!r}"
                    )


def _write_step_closures(base: Path, claims: dict[str, WorkflowStage]) -> dict[str, dict[int, Path]]:
    """Generate one sh closure per claimed step under the container-local base.

    Args:
        base: The container-local closure base directory (created owner-only).
        claims: The stage-id → workflow stage map of the delivery.

    Returns:
        The stage-id → (step-index → wrapper path) map — one entry per
        env-carrying step; the file name composes the stage id, the step
        index, and the step name through the shared safe-name helper, so two
        steps of one stage never collide (step names are not unique-checked).
    """
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    # mkdir(exist_ok=True) keeps the mode of an existing directory — pin it
    # so a pre-existing base never widens the closure visibility.
    base.chmod(0o700)

    wrappers: dict[str, dict[int, Path]] = {}

    for stage_id, wstage in claims.items():
        stage_wrappers: dict[int, Path] = {}

        for index, step in enumerate(wstage.gates):
            if step.env is None:
                continue

            path = base / _wrapper_file_name(f"{stage_id}-{index}-{step.name}")
            _write_owner_only(path, _render_step_closure(step.script, step.agent, step.env))
            stage_wrappers[index] = path

        wrappers[stage_id] = stage_wrappers

    return wrappers


def apply_gate_env_wrappers(
    stages: list[FlowStage],
    workflow: WorkflowDocument | None,
    flow_path: Path,
) -> list[FlowStage]:
    """Deliver the per-step gate env instructions of a compiled flow.

    Every workflow stage whose gates carry at least one non-empty step env
    map claims its compiled stage (by exact id, then by the
    ``<name>-<digits>`` loop-expansion suffix — exact beats suffix); each
    claimed step receives one sh closure wrapper under a container-local
    temp directory exporting its env values verbatim, and its ``run``
    (a script step) or ``command`` (an agent step) field in the ALREADY
    WRITTEN flow-file is patched to point at the wrapper. With no claims the
    input list returns unchanged and the flow-file is neither read nor
    written (the env-free invariant).

    Args:
        stages: The compiled flow stages.
        workflow: The effective workflow document (its stages map carries the
            gate instructions), or ``None`` (no step is wrapped).
        flow_path: The path of the flow-file written by ``compile_flow`` —
            the target of the post-compile verify-step patch.

    Returns:
        The new stage list — claimed stages are new objects carrying rebuilt
        ``verify`` gates whose env steps point at their wrappers; every other
        stage is the SAME input object.

    Raises:
        ValueError: When a claimed step's env key is not a legal environment
            variable name (naming the stage, the step, and the key — raised
            before any wrapper file is written), or when a claimed stage
            matches no verify block in the flow-file.
    """
    if workflow is None:
        return stages

    claims = _select_gate_claims(stages, workflow)

    if not claims:
        return stages

    _validate_env_names(claims)
    wrappers = _write_step_closures(_GATE_WRAPPER_BASE, claims)

    text = flow_path.read_text()

    for stage_id, stage_wrappers in wrappers.items():
        for index, path in stage_wrappers.items():
            text = _patch_verify_step(text, stage_id, index, str(path))

    flow_path.write_text(text)

    logger.info("wrote gate env wrappers", extra={"stages": sorted(wrappers)})

    return [
        _patched_stage(stage, wrappers[stage.id], claims[stage.id].gates)
        if stage.id in wrappers and stage.fields.get("verify") is not None
        else stage
        for stage in stages
    ]
