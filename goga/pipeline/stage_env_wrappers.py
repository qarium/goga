"""The ``apply_stage_env_wrappers`` routine — the per-stage sh closures delivering env layers."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shlex
from pathlib import Path

import yaml

from ..agents import resolve_wrapper_path
from .compiler import FlowStage
from .workflow import WorkflowDocument, WorkflowStage

logger = logging.getLogger(__name__)

# The container-local base directory of the generated closures — never under
# /workspace or the project directory. A module constant so the tests (and
# only they) can relocate it.
_WRAPPER_BASE = Path("/tmp/goga-stage-env")

# The serialized flow-file stage keys that follow ``command`` in the
# compiler's canonical order — the insertion anchors when a claimed stage
# carries no ``command`` line. ``verify`` is the canonical tail (after
# ``assistants``; the compiler's gate and stage assistant entries nest at
# four-plus spaces, so the ``  command:`` rewrite is unaffected); the
# stage-block span detection is bounded to the ``stages:`` section, so a
# ``team:`` member named like a stage never captures the patch;
# ``depends_on`` serializes last (after every canonical and unknown key), so
# it anchors the tail position; a block with neither an anchor nor
# ``depends_on`` takes the insert at its end.
_KEYS_AFTER_COMMAND = (
    "prompt",
    "description",
    "buttons",
    "agents",
    "supervisor",
    "supervisor_prompt",
    "skills",
    "script_before",
    "script",
    "script_after",
    "script_timeout",
    "reflect",
    "memory_use",
    "assistants",
    "verify",
)

# Stage ids that double as a safe file name are used verbatim; anything else
# is sanitized plus a short digest suffix (deterministic, collision-free).
# An all-dot id is never safe verbatim — "." and ".." are the directory
# aliases themselves, so they flow through the sanitize branch like any
# other unsafe id.
_SAFE_NAME_PATTERN = re.compile(r"[A-Za-z0-9._-]+")
_UNSAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]")

# A legal environment variable name per POSIX — the only shape ``export
# KEY=value`` in a generated sh closure accepts; anything else (a shell
# metacharacter, a non-str YAML key) would inject or break the script.
_LEGAL_ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# The serialized stage-block header (``- id: NAME`` at column 0) and a
# first-level stage field line (``  KEY:`` at exactly two spaces — deeper
# indented lines are nested map entries or block-literal continuations).
_HEADER_PATTERN = re.compile(r"^- id: (.*)$")
_FIELD_PATTERN = re.compile(r"^  ([^\s:][^:]*):")

# The indent of a first-level stage field line — the ``  script:`` patch's
# block-literal boundary.
_FIELD_INDENT = 2


def _line_indent(line: str) -> int:
    """Measure one serialized line's leading-space indent.

    Args:
        line: The serialized flow-file line (``splitlines(keepends=True)`` form).

    Returns:
        The number of leading spaces.
    """
    return len(line) - len(line.lstrip(" "))

# The top-level ``stages:`` key — the section boundary of the stage blocks.
# The serializer emits the ``team:`` list BEFORE ``stages:`` with member
# headers shaped exactly like stage headers (``- id: NAME`` at column 0), so
# a stage-block search must start after this line to never land inside a team
# member block.
_STAGES_SECTION = "stages:\n"


def _select_claims(
    stages: list[FlowStage],
    workflow: WorkflowDocument,
) -> dict[str, tuple[str, WorkflowStage]]:
    """Map every env-claiming stage id to its declaring workflow stage.

    Args:
        stages: The compiled flow stages — the claim targets.
        workflow: The effective workflow document (its stages map carries the
            env instructions).

    Returns:
        The stage-id → (workflow stage name, workflow stage) map — the name is
        the declaring entry's key (the loop-expansion base of a suffix claim),
        carried for the extend-entry agent tier of the exec-target resolution.
        Exact id matches claim first (across every workflow name — exact beats
        suffix); the remaining ids are then claimed by the ``<name>-<digits>``
        loop-expansion suffix of a workflow stage name.
    """
    env_entries = [(name, stage) for name, stage in workflow.stages.items() if stage.env is not None]
    claims: dict[str, tuple[str, WorkflowStage]] = {}

    for name, wstage in env_entries:
        for stage in stages:
            if stage.id == name:
                claims[stage.id] = (name, wstage)

    for name, wstage in env_entries:
        suffix_pattern = re.compile(rf"{re.escape(name)}-\d+")

        for stage in stages:
            if stage.id not in claims and suffix_pattern.fullmatch(stage.id):
                claims[stage.id] = (name, wstage)

    return claims


def _resolve_exec_target(
    wstage: WorkflowStage,
    extend_agent: str | None,
    global_agent: str | None,
    stage_id: str,
) -> str:
    """Resolve the exec target of one claimed stage.

    Args:
        wstage: The declaring workflow stage — its ``agent`` wins.
        extend_agent: The extend-entry agent of the same workflow stage name —
            the compiler's per-field default (an explicit stages-block agent
            wins over it), the middle fallback.
        global_agent: The effective global pipeline agent — the last fallback.
        stage_id: The claimed stage id (used in the error message).

    Returns:
        The resolved in-container wrapper path of the stage agent, the
        extend-entry agent, or the global agent — the same precedence the
        compiler used to compose the pre-patch ``command``.

    Raises:
        ValueError: When no tier resolved an agent — a strict pre-run error
            naming the stage.
    """
    if wstage.agent is not None:
        return resolve_wrapper_path(wstage.agent)

    if extend_agent is not None:
        return resolve_wrapper_path(extend_agent)

    if global_agent is not None:
        return resolve_wrapper_path(global_agent)

    raise ValueError(f"stage {stage_id} declares env but resolved no agent: set its agent or a global agent")


def _wrapper_file_name(stage_id: str) -> str:
    """Compose the wrapper file name of one claimed stage.

    Args:
        stage_id: The claimed stage id.

    Returns:
        The stage id itself when it is a safe file name, else its sanitized
        form plus an 8-hex-digit digest of the original id.
    """
    if _SAFE_NAME_PATTERN.fullmatch(stage_id) and set(stage_id) != {"."}:
        return stage_id

    sanitized = _UNSAFE_NAME_PATTERN.sub("_", stage_id)
    digest = hashlib.sha256(stage_id.encode()).hexdigest()[:8]

    return f"{sanitized}-{digest}"


def _write_owner_only(path: Path, script: str) -> None:
    """Write one closure file owner-accessible from the first byte.

    Args:
        path: The closure file path.
        script: The rendered sh closure text.

    Creates the file with mode 0o700 (never create-then-chmod, which leaves a
    umask-defaulted window in which the exported env layer is readable).
    """
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o700)

    with os.fdopen(descriptor, "w") as handle:
        handle.write(script)


def _render_script(env: dict[str, str], target: str) -> str:
    """Render one agent stage's sh closure: export the env, then exec the target.

    Args:
        env: The stage's authored env map — exported VERBATIM (no engine-key
            dropping; per-stage layers sit above all global layers).
        target: The resolved in-container wrapper path — the exec target.

    Returns:
        The script text: the shebang, one ``export`` line per entry (values
        shell-quoted), and the exec line (the target shell-quoted) forwarding
        ``"$@"``.
    """
    exports = "".join(f"export {key}={shlex.quote(value)}\n" for key, value in env.items())

    return f'#!/bin/sh\n{exports}exec {shlex.quote(target)} "$@"\n'


def _render_payload_closure(env: dict[str, str], script: str) -> str:
    """Render one script stage's sh closure: export the env, then carry the payload.

    Args:
        env: The stage's authored env map — exported VERBATIM (no engine-key
            dropping; per-stage layers sit above all global layers).
        script: The stage's authored script — the compiled ``script`` field
            value (the stage's action; the compiler assembles no ``command``
            beside it).

    Returns:
        The script text: the shebang, one ``export`` line per entry (values
        shell-quoted), then the payload — the authored script lines as-is
        (the same shell, working directory, and exit status the engine gives
        the authored ``script`` value) — the gate script-step closure shape.
    """
    exports = "".join(f"export {key}={shlex.quote(value)}\n" for key, value in env.items())
    payload = script if script.endswith("\n") else script + "\n"

    return f"#!/bin/sh\n{exports}{payload}"


def _header_matches(line: str, stage_id: str) -> bool:
    """Test one serialized line for being the ``- id:`` header of ``stage_id``.

    Args:
        line: A serialized flow-file line.
        stage_id: The claimed stage id.

    Returns:
        ``True`` when the line is the stage's block header — the id compared
        both as the raw scalar text and through a YAML scalar parse (ids the
        serializer had to quote still match).
    """
    match = _HEADER_PATTERN.match(line)

    if match is None:
        return False

    if match.group(1) == stage_id:
        return True

    try:
        return yaml.safe_load(match.group(1)) == stage_id
    except yaml.YAMLError:
        return False


def _find_stage_block(lines: list[str], stage_id: str) -> tuple[int, int]:
    """Locate one stage's serialized block inside the ``stages:`` section.

    Args:
        lines: The flow-file lines (``splitlines(keepends=True)``).
        stage_id: The claimed stage id.

    Returns:
        The ``(header_index, end_index)`` span — end exclusive. Block member
        lines are the header plus every following line indented at least two
        spaces (nested entries and block-literal continuations included) and
        every blank line between them (the serializer emits truly empty lines
        INSIDE multi-line scalars — a quoted or literal value with paragraph
        breaks); the next non-blank column-0 line ends the block. The header
        search starts AFTER the top-level ``stages:`` line — the ``team:`` list
        that precedes it serializes member headers (``- id: NAME`` at column
        0) indistinguishable from stage headers, and an assistant named like a
        stage must never capture the stage's patch.

    Raises:
        ValueError: When the flow-file carries no top-level ``stages:`` line
            or no block header matches the stage id (the flow-file and the
            stage list disagree — an internal invariant breach).
    """
    stages_at = next((i for i, line in enumerate(lines) if line == _STAGES_SECTION), None)

    if stages_at is None:
        raise ValueError("flow-file carries no top-level stages: section")

    start = next(
        (i for i, line in enumerate(lines[stages_at + 1 :], stages_at + 1) if _header_matches(line, stage_id)),
        None,
    )

    if start is None:
        raise ValueError(f"stage {stage_id!r} missing from the flow-file")

    end = start + 1

    while end < len(lines) and (lines[end].startswith("  ") or not lines[end].strip()):
        end += 1

    return start, end


def _patch_stage_command(text: str, stage_id: str, wrapper: str) -> str:
    """Rewrite exactly one stage's ``command`` field in the serialized text.

    Args:
        text: The flow-file text.
        stage_id: The claimed stage id.
        wrapper: The absolute wrapper path — the new command value.

    Returns:
        The patched text. An existing ``command`` line is rewritten in place;
        an absent one is inserted at the canonical position — before the
        first present canonical key after ``command``, else before
        ``depends_on``, else at the block end. Every other byte stays
        untouched (a targeted text patch, never a YAML round-trip).
    """
    lines = text.splitlines(keepends=True)
    start, end = _find_stage_block(lines, stage_id)
    body = lines[start + 1 : end]

    for index, line in enumerate(body):
        if line.startswith("  command:"):
            body[index] = f"  command: {wrapper}\n"
            break
    else:
        anchors = (*_KEYS_AFTER_COMMAND, "depends_on")
        insert_at = len(body)

        for index, line in enumerate(body):
            match = _FIELD_PATTERN.match(line)

            if match is not None and match.group(1) in anchors:
                insert_at = index
                break

        body.insert(insert_at, f"  command: {wrapper}\n")

    return "".join(lines[: start + 1] + body + lines[end:])


def _field_value_end(body: list[str], field_at: int, field_indent: int) -> int:
    """Measure the exclusive end of a stage field's serialized value.

    Args:
        body: The stage block's member lines (``splitlines(keepends=True)``
            form, without the ``- id:`` header).
        field_at: The offset of the ``  script:`` field line.
        field_indent: The field line's indent (a first-level stage field —
            two spaces).

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


def _patch_stage_script(text: str, stage_id: str, wrapper: str) -> str:
    """Rewrite exactly one script stage's ``script`` field in the serialized text.

    Args:
        text: The flow-file text.
        stage_id: The claimed stage id — locates the stage block.
        wrapper: The absolute wrapper path — the new script value.

    Returns:
        The patched text. The ``  script:`` line (exact two-space field
        indent — ``script_before:``/``script_after:`` never match the prefix)
        is rewritten in place; a block-literal old value (a multi-line
        authored script) is consumed with its continuation lines. Every other
        byte stays untouched (a targeted text patch, never a YAML round-trip).

    Raises:
        ValueError: When the stage block carries no ``  script:`` field (the
            flow-file and the compiled stage disagree — an internal invariant
            breach).
    """
    lines = text.splitlines(keepends=True)
    start, end = _find_stage_block(lines, stage_id)
    body = lines[start + 1 : end]

    field_at = next((i for i, line in enumerate(body) if line.startswith("  script:")), None)

    if field_at is None:
        raise ValueError(f"stage {stage_id!r} carries no script field in the flow-file")

    value_end = _field_value_end(body, field_at, _FIELD_INDENT)
    body[field_at:value_end] = [f"  script: {wrapper}\n"]

    return "".join(lines[: start + 1] + body + lines[end:])


def _with_command(stage: FlowStage, command: str) -> FlowStage:
    """Build one claimed stage's replacement with its command field rewritten.

    Args:
        stage: The compiled stage — read-only input.
        command: The absolute wrapper path.

    Returns:
        A new ``FlowStage`` carrying a fresh fields dict with ``command`` set
        (an existing command keeps its position in the key order). The input
        object and its fields dict are never mutated.
    """
    fields = dict(stage.fields)
    fields["command"] = command

    return FlowStage(id=stage.id, name=stage.name, depends_on=stage.depends_on, fields=fields)


def _with_script(stage: FlowStage, wrapper: str) -> FlowStage:
    """Build one claimed script stage's replacement with its script field rewritten.

    Args:
        stage: The compiled stage — read-only input.
        wrapper: The absolute wrapper path.

    Returns:
        A new ``FlowStage`` carrying a fresh fields dict with ``script`` set
        (the field keeps its position in the key order). The input object and
        its fields dict are never mutated.
    """
    fields = dict(stage.fields)
    fields["script"] = wrapper

    return FlowStage(id=stage.id, name=stage.name, depends_on=stage.depends_on, fields=fields)


def apply_stage_env_wrappers(
    stages: list[FlowStage],
    workflow: WorkflowDocument | None,
    global_agent: str | None,
    flow_path: Path,
) -> list[FlowStage]:
    """Deliver the per-stage env instructions of a compiled flow.

    Every env-declaring workflow stage claims its compiled stage (by exact
    id, then by the ``<name>-<digits>`` loop-expansion suffix — exact beats
    suffix); each claimed stage receives one sh closure wrapper under a
    container-local temp directory exporting its env values verbatim. The
    delivery form follows the claimed stage's own compiled fields: a script
    stage (a stage carrying a ``script`` field — the stage's action, with no
    agent command) receives a payload closure carrying the authored script
    lines as-is and its ``script`` field in the ALREADY WRITTEN flow-file is
    patched to point at the wrapper; every other stage receives an exec
    closure over the resolved agent wrapper and its ``command`` field is
    patched (inserted when the compiler emitted none). With no claims the
    input list returns unchanged and the flow-file is neither read nor
    written (the env-free invariant).

    Args:
        stages: The compiled flow stages.
        workflow: The effective workflow document (its stages map carries
            the env instructions), or ``None`` (no stage is wrapped).
        global_agent: The effective global pipeline agent — the fallback
            exec target when a claimed agent stage resolved neither its own
            agent nor an extend-entry agent of the same name (a script stage
            resolves no exec target at all).
        flow_path: The path of the flow-file written by ``compile_flow`` —
            the target of the post-compile script/command patch.

    Returns:
        The new stage list — claimed script stages are new objects carrying
        ``script`` fields pointing at their wrappers, every other claimed
        stage carries a ``command`` field pointing at its wrapper; every
        unclaimed stage is the SAME input object.

    Raises:
        ValueError: When a claimed agent stage resolved no exec target (no
            stage agent and no global agent — a strict pre-run error naming
            the stage), when a declared env key is not a legal environment
            variable name (naming the stage and the key — raised before any
            wrapper file is written), or when a claimed stage id matches no
            block in the flow-file.
    """
    if workflow is None:
        return stages

    claims = _select_claims(stages, workflow)

    if not claims:
        return stages

    compiled = {stage.id: stage for stage in stages}
    script_claims = {stage_id for stage_id in claims if "script" in compiled[stage_id].fields}
    agent_claims = {stage_id for stage_id in claims if stage_id not in script_claims}

    targets = {
        stage_id: _resolve_exec_target(
            claims[stage_id][1],
            workflow.extend[claims[stage_id][0]].agent if claims[stage_id][0] in workflow.extend else None,
            global_agent,
            stage_id,
        )
        for stage_id in agent_claims
    }

    # Validate every declared env key BEFORE writing any file: a key that is
    # not a legal environment variable name would inject shell metacharacters
    # into (or break) the generated export line — a strict pre-run error, so
    # no partial wrapper set can reach a stage launch. The claims invariant
    # guarantees a non-None (non-empty) env map on every claimed stage.
    for stage_id, (_, wstage) in claims.items():
        for key in wstage.env:
            if _LEGAL_ENV_NAME_PATTERN.fullmatch(key) is None:
                raise ValueError(f"invalid environment variable name in the {stage_id} stage env: {key!r}")

    base = _WRAPPER_BASE
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    # mkdir(exist_ok=True) keeps the mode of an existing directory — pin it
    # so a pre-existing base never widens the closure visibility.
    base.chmod(0o700)

    wrappers: dict[str, Path] = {}

    for stage_id in script_claims:
        path = base / _wrapper_file_name(stage_id)
        _write_owner_only(path, _render_payload_closure(claims[stage_id][1].env, compiled[stage_id].fields["script"]))
        wrappers[stage_id] = path

    for stage_id, target in targets.items():
        path = base / _wrapper_file_name(stage_id)
        _write_owner_only(path, _render_script(claims[stage_id][1].env, target))
        wrappers[stage_id] = path

    text = flow_path.read_text()

    for stage_id, path in wrappers.items():
        patch = _patch_stage_script if stage_id in script_claims else _patch_stage_command
        text = patch(text, stage_id, str(path))

    flow_path.write_text(text)

    logger.info("wrote stage env wrappers", extra={"stages": sorted(wrappers)})

    return [
        _with_script(stage, str(wrappers[stage.id]))
        if stage.id in script_claims
        else _with_command(stage, str(wrappers[stage.id]))
        if stage.id in wrappers
        else stage
        for stage in stages
    ]
