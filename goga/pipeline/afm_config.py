"""In-container authorship of the afm configuration file."""

from __future__ import annotations

import logging
import os
import re
import shlex
from pathlib import Path

import yaml

from ..agents import resolve_wrapper_path
from .compiler import FlowDocument
from .workflow import WorkflowAssistant, WorkflowDocument

logger = logging.getLogger(__name__)

_AFM_CONFIG_PATH = Path("/home/goga/.afm/config.yaml")
_PROMPTS_DIR = "/home/goga/pipeline/prompts"

# The container-local base directory of the generated assistant env closures —
# never under /workspace or the project directory. A module constant so the
# tests (and only they) can relocate it.
_CLOSURE_BASE = Path("/tmp/goga-assistant-env")

# A legal environment variable name per POSIX — the only shape ``export
# KEY=value`` in a generated sh closure accepts; anything else (a shell
# metacharacter, a non-str YAML key) would inject or break the script.
_LEGAL_ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# The generated profile binding prefix — goga's channel inside the engine's
# profile namespace (a user-authored same-named project-layer profile
# deliberately overrides the plumbing; that file is never touched here).
_PROFILE_PREFIX = "goga-"


def _is_assistant_declaration(entry: WorkflowAssistant) -> bool:
    """Report whether ``entry`` is a declaration (a prompt or a skills list is authored).

    Args:
        entry: One catalog entry or attachment entry of the workflow. The
            discriminator is PRESENCE, not truthiness — ``prompt: ""`` and
            ``skills: []`` are authored values that make the entry a
            declaration; a reference carries neither field.

    Returns:
        ``True`` when ``entry.prompt is not None or entry.skills is not None``
        — the one-line declaration rule shared by every consuming cell.
    """
    return entry.prompt is not None or entry.skills is not None


def _assistant_namespace(workflow: WorkflowDocument) -> dict[str, tuple[WorkflowAssistant, str]]:
    """Build the assistant namespace with each declaration's authoring site.

    Args:
        workflow: The effective workflow document. The catalog comes first
            (authored order), then every inline stage declaration in authored
            stage order. The parser (and the overlay merge) already guarantee
            no duplicate names, so a later declaration can never shadow a
            catalog entry of the same name.

    Returns:
        The name → (declaration, site) map — the site is
        ``"workflow.assistants"`` for a catalog entry and
        ``"workflow.stages.<stage>"`` for an inline declaration (the
        no-agent pre-run error names it).
    """
    namespace: dict[str, tuple[WorkflowAssistant, str]] = {
        name: (entry, "workflow.assistants") for name, entry in workflow.assistants.items()
    }

    for stage_name, stage in workflow.stages.items():
        for entry in (stage.assistants or {}).values():
            if _is_assistant_declaration(entry):
                namespace[entry.name] = (entry, f"workflow.stages.{stage_name}")

    return namespace


def _referenced_names(flow: FlowDocument) -> list[str]:
    """Collect the flow-referenced assistant names in emission order, deduplicated.

    Args:
        flow: The compiled flow document — the single source of truth for
            which profile ids exist. Team members come first, then every
            stage attachment entry in stage order.

    Returns:
        The ordered-unique name list — a name referenced both as a team
        member and as a stage attachment collapses to one entry.
    """
    names = [member.id for member in flow.team or []]
    names += [entry.title for stage in flow.stages for entry in stage.fields.get("assistants", [])]

    seen: set[str] = set()
    unique: list[str] = []

    for name in names:
        if name not in seen:
            seen.add(name)
            unique.append(name)

    return unique


def _resolve_profiles(
    agent: str | None,
    flow: FlowDocument,
    namespace: dict[str, tuple[WorkflowAssistant, str]],
) -> dict[str, tuple[bool, dict[str, str] | None, str]]:
    """Resolve every referenced assistant in memory — no file is touched here.

    Args:
        agent: The effective global pipeline agent — the fallback tier when a
            declaration carries no agent of its own.
        flow: The compiled flow document (the referenced names source).
        namespace: The name → (declaration, site) map of the workflow.

    Returns:
        The name → (delegate, env, wrapper) map — every command resolved to
        its absolute wrapper path.

    Raises:
        ValueError: When the flow references a name the workflow does not
            declare (the defensive branch), when a declared env key is not a
            legal environment variable name, or when an assistant resolves no
            agent at all — every check fires before any file is written.
    """
    resolved: dict[str, tuple[bool, dict[str, str] | None, str]] = {}

    for name in _referenced_names(flow):
        entry_site = namespace.get(name)

        if entry_site is None:
            raise ValueError(f"unknown assistant reference in the compiled flow: {name}")

        declaration, site = entry_site

        if declaration.env is not None:
            for key in declaration.env:
                if _LEGAL_ENV_NAME_PATTERN.fullmatch(key) is None:
                    raise ValueError(f"invalid environment variable name in the {name} assistant env: {key!r}")

        target_agent = declaration.agent if declaration.agent is not None else agent

        if target_agent is None:
            raise ValueError(
                f"assistant {name} at {site} "
                f"{'declares env but ' if declaration.env is not None else ''}"
                f"resolved no agent: set its agent or a global agent"
            )

        # The model's tri-state collapses to the engine's bool exactly once,
        # here at the delivery boundary — None (not authored) is False.
        delegate = declaration.delegate if declaration.delegate is not None else False

        resolved[name] = (delegate, declaration.env, resolve_wrapper_path(target_agent))

    return resolved


def _render_closure(env: dict[str, str], target: str) -> str:
    """Render one assistant's sh closure: export the env, then exec the target.

    Args:
        env: The assistant's authored env map — exported VERBATIM (values
            shell-quoted).
        target: The resolved in-container wrapper path — the exec target.

    Returns:
        The script text: the shebang, one ``export`` line per entry, and the
        exec line forwarding ``"$@"`` — the same content contract as the
        per-stage env closures.
    """
    exports = "".join(f"export {key}={shlex.quote(value)}\n" for key, value in env.items())

    return f'#!/bin/sh\n{exports}exec {shlex.quote(target)} "$@"\n'


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


def _collaboration_section(
    agent: str | None,
    flow: FlowDocument,
    workflow: WorkflowDocument,
) -> dict[str, object]:
    """Materialize the collaboration plumbing — profiles and the task budget.

    Args:
        agent: The effective global pipeline agent — the command fallback
            tier of every generated profile.
        flow: The compiled flow document — the single source of truth for
            which profile ids exist (a profile is materialized exactly for
            the ids the flow references; an attachment removed by a stage
            skip never appears in the flow, so no dead profile remains).
        workflow: The effective workflow document — the source of each
            referenced assistant's declaration (agent, delegate, env) and of
            the delegation block.

    Returns:
        The ``collaboration`` section: ``profiles`` (one
        ``goga-<name>`` entry per referenced id, each exactly
        ``{title, command, delegate}`` — an env-declaring assistant's command
        is its generated closure path) and ``limits`` (only when the workflow
        carries a delegation block).

    Raises:
        ValueError: Every resolution error of ``_resolve_profiles`` — all of
            them fire before any file (config or closure) is written.
    """
    resolved = _resolve_profiles(agent, flow, _assistant_namespace(workflow))

    _CLOSURE_BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
    # mkdir(exist_ok=True) keeps the mode of an existing directory — pin it
    # so a pre-existing base never widens the closure visibility.
    _CLOSURE_BASE.chmod(0o700)

    profiles: dict[str, dict[str, object]] = {}

    for name, (delegate, env, target) in resolved.items():
        command = target

        if env is not None:
            path = _CLOSURE_BASE / f"{_PROFILE_PREFIX}{name}"
            _write_owner_only(path, _render_closure(env, target))
            command = str(path)

        profiles[f"{_PROFILE_PREFIX}{name}"] = {"title": name, "command": command, "delegate": delegate}

    section: dict[str, object] = {"profiles": profiles}

    if workflow.delegation is not None:
        section["limits"] = {"max_tasks": workflow.delegation.max_tasks}

    return section


def write_afm_config(
    agent: str | None,
    flow: FlowDocument | None = None,
    workflow: WorkflowDocument | None = None,
) -> Path:
    """Write the whole afm configuration file at the fixed in-container home path.

    Args:
        agent: The effective pipeline agent as amended by the config delivery
            (e.g. "codex"); ``None`` omits the whole ``client`` block.
        flow: The compiled flow document — the source of the generated
            profile ids (the binding of every team member and of every stage
            attachment the flow carries); ``None`` (with a ``workflow`` given
            or alone) writes no collaboration plumbing.
        workflow: The effective workflow document — the source of each
            referenced assistant's declaration (agent, delegate, env) and of
            the delegation block; ``None`` (with a ``flow`` given or alone)
            writes no collaboration plumbing.

    Returns:
        The fixed in-container path of the written file
        (``/home/goga/.afm/config.yaml``), independent of ``AFM_DIR``. The
        content serializes the optional ``client`` block first (the
        ``client.command`` default for stages without a per-stage ``command:``
        override), then the four static launcher fields — ``theme: goga``,
        ``open_browser: false``, ``proxy.enabled: false``, and ``prompts_dir:
        /home/goga/pipeline/prompts`` — never configurable through the project
        configuration or the CLI — goga's observer hook registration: a
        ``hooks`` list carrying the single ``goga`` entry (``events: all``,
        the bridge command ``python3 -m goga.pipeline hook``,
        ``inherit_env: true``; ``timeout`` / ``retries`` omitted — the afm
        ``omitempty`` defaults 30 s / 0 — and no ``env`` map); and finally the
        ``collaboration`` section when both ``flow`` and ``workflow`` are
        given — one generated ``goga-<name>`` profile per flow-referenced id
        (exactly ``{title, command, delegate}``; an env-declaring assistant's
        command is its generated owner-only closure path) and
        ``limits.max_tasks`` only when the workflow carries a delegation
        block.

    Raises:
        ValueError: When a referenced assistant's declared env carries an
            illegal environment variable name, when an assistant resolves no
            agent at all (no own agent, no global agent), or — defensively —
            when the compiled flow references a name the workflow does not
            declare; every variant fires before any file (config or closure)
            is written.
        OSError: When the home directory is unwritable — propagates unchanged
            (the caller returns before any run event fires; no partial file is
            left behind).
    """
    wrapper = resolve_wrapper_path(agent) if agent is not None else None

    content: dict[str, object] = {}
    if wrapper is not None:
        content["client"] = {"command": wrapper}

    content.update(
        {
            "theme": "goga",
            "open_browser": False,
            "proxy": {"enabled": False},
            "prompts_dir": _PROMPTS_DIR,
        }
    )
    content["hooks"] = [
        {
            "id": "goga",
            "events": "all",
            "command": "python3 -m goga.pipeline hook",
            "inherit_env": True,
        }
    ]

    collaboration: dict[str, object] | None = None

    if flow is not None and workflow is not None:
        collaboration = _collaboration_section(agent, flow, workflow)
        content["collaboration"] = collaboration

    _AFM_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _AFM_CONFIG_PATH.write_text(yaml.safe_dump(content, default_flow_style=False, sort_keys=False))

    if collaboration is not None:
        logger.info(
            "wrote afm collaboration plumbing",
            extra={"profiles": len(collaboration["profiles"]), "has_limits": "limits" in collaboration},
        )

    return _AFM_CONFIG_PATH
