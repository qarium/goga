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
# carries no ``command`` line. ``depends_on`` serializes last (after every
# canonical and unknown key), so it anchors the tail position; a block with
# neither an anchor nor ``depends_on`` takes the insert at its end.
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
)

# Stage ids that double as a safe file name are used verbatim; anything else
# is sanitized plus a short digest suffix (deterministic, collision-free).
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
    if _SAFE_NAME_PATTERN.fullmatch(stage_id):
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
    """Render one stage's sh closure: export the env, then exec the target.

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
    """Locate one stage's serialized block.

    Args:
        lines: The flow-file lines (``splitlines(keepends=True)``).
        stage_id: The claimed stage id.

    Returns:
        The ``(header_index, end_index)`` span — end exclusive. Block member
        lines are the header plus every following line indented at least two
        spaces (nested entries and block-literal continuations included) and
        every blank line between them (the serializer emits truly empty lines
        INSIDE multi-line scalars — a quoted or literal value with paragraph
        breaks); the next non-blank column-0 line ends the block.

    Raises:
        ValueError: When no block header matches the stage id (the flow-file
            and the stage list disagree — an internal invariant breach).
    """
    start = next((i for i, line in enumerate(lines) if _header_matches(line, stage_id)), None)

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
    container-local temp directory exporting its env values verbatim, and
    its ``command`` field in the ALREADY WRITTEN flow-file is patched to
    point at the wrapper. With no claims the input list returns unchanged
    and the flow-file is neither read nor written (the env-free invariant).

    Args:
        stages: The compiled flow stages.
        workflow: The effective workflow document (its stages map carries
            the env instructions), or ``None`` (no stage is wrapped).
        global_agent: The effective global pipeline agent — the fallback
            exec target when a claimed workflow stage resolved neither its
            own agent nor an extend-entry agent of the same name.
        flow_path: The path of the flow-file written by ``compile_flow`` —
            the target of the post-compile command patch.

    Returns:
        The new stage list — claimed stages are new objects carrying
        ``command`` fields pointing at their wrappers; every other stage is
        the SAME input object.

    Raises:
        ValueError: When a claimed stage resolved no exec target (no stage
            agent and no global agent — a strict pre-run error naming the
            stage), when a declared env key is not a legal environment
            variable name (naming the stage and the key — raised before any
            wrapper file is written), or when a claimed stage id matches no
            block in the flow-file.
    """
    if workflow is None:
        return stages

    claims = _select_claims(stages, workflow)

    if not claims:
        return stages

    targets = {
        stage_id: _resolve_exec_target(
            wstage,
            workflow.extend[name].agent if name in workflow.extend else None,
            global_agent,
            stage_id,
        )
        for stage_id, (name, wstage) in claims.items()
    }

    # Validate every declared env key BEFORE writing any file: a key that is
    # not a legal environment variable name would inject shell metacharacters
    # into (or break) the generated export line — a strict pre-run error, so
    # no partial wrapper set can reach a stage launch.
    for stage_id, (_, wstage) in claims.items():
        for key in wstage.env or {}:
            if _LEGAL_ENV_NAME_PATTERN.fullmatch(key) is None:
                raise ValueError(f"invalid environment variable name in the {stage_id} stage env: {key!r}")

    base = _WRAPPER_BASE
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    # mkdir(exist_ok=True) keeps the mode of an existing directory — pin it
    # so a pre-existing base never widens the closure visibility.
    base.chmod(0o700)

    wrappers: dict[str, Path] = {}

    for stage_id, target in targets.items():
        path = base / _wrapper_file_name(stage_id)
        _write_owner_only(path, _render_script(claims[stage_id][1].env or {}, target))
        wrappers[stage_id] = path

    text = flow_path.read_text()

    for stage_id, path in wrappers.items():
        text = _patch_stage_command(text, stage_id, str(path))

    flow_path.write_text(text)

    logger.info("wrote stage env wrappers", extra={"stages": sorted(wrappers)})

    return [_with_command(stage, str(wrappers[stage.id])) if stage.id in wrappers else stage for stage in stages]
