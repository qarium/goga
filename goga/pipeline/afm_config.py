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
# The engine's custom skin directory: afm serves it wholesale as the active
# skin only while it holds index.css DIRECTLY inside (the engine's builtin
# theme is then just the fallback). Must equal _SKINS_TARGET_BASE/_SKIN_NAME of
# afm_skin.
_SKIN_DIR = "/home/goga/.afm/skins/goga"

# The collaboration execution context goga always declares — every command the
# engine spawns for the run (client and generated profiles alike) is an
# as-claude wrapper, so the wrapper context is the static delivery decision,
# never a project-configurable field.
_RUNTIME_CONTEXT = "wrapper"

# Hide dynamic attach helpers button
_HIDE_ATTACH_HELPERS = True

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
    """Return ``True`` when ``entry`` is a declaration (any of the five authoring fields is present).

    Args:
        entry: One catalog entry or attachment entry of the workflow. The
            discriminator is PRESENCE, not truthiness — ``prompt: ""``,
            ``skills: []``, and ``env: {}`` are authored values that make
            the entry a declaration; a reference carries none of the five
            fields (``gate``/``when`` are attachment parameters, never
            content).

    Returns:
        ``True`` when any of ``prompt``, ``skills``, ``agent``, ``delegate``,
        ``env`` is not ``None`` — the five-field declaration rule shared by
        every consuming cell.
    """
    return (
        entry.prompt is not None
        or entry.skills is not None
        or entry.agent is not None
        or entry.delegate is not None
        or entry.env is not None
    )


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


def _wrapper_agent_label(command: str) -> str | None:
    """Return the bare agent id of an ``<agent>-as-claude.sh`` wrapper path, else ``None``.

    The engine's dashboard label falls back to the file base name (``claude-as-claude.sh``);
    the generated ``command_names`` section maps every wrapper to the bare agent id.
    """
    suffix = "-as-claude.sh"
    base = Path(command).name

    if not base.endswith(suffix):
        return None

    return base[: -len(suffix)]


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
            declare (the defensive branch), when an env key of a NON-EMPTY
            effective env map is not a legal environment variable name, or
            when an assistant resolves no agent at all — every check fires
            before any file is written.
    """
    resolved: dict[str, tuple[bool, dict[str, str] | None, str]] = {}

    for name in _referenced_names(flow):
        entry_site = namespace.get(name)

        if entry_site is None:
            raise ValueError(f"unknown assistant reference in the compiled flow: {name}")

        declaration, site = entry_site

        # None and {} both mean "no closure" — the env delivery keys on a
        # non-empty effective map only (an explicitly cleared env is no env).
        if declaration.env:
            for key in declaration.env:
                if _LEGAL_ENV_NAME_PATTERN.fullmatch(key) is None:
                    raise ValueError(f"invalid environment variable name in the {name} assistant env: {key!r}")

        target_agent = declaration.agent if declaration.agent is not None else agent

        if target_agent is None:
            raise ValueError(
                f"assistant {name} at {site} "
                f"{'declares env but ' if declaration.env else ''}"
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
        The ``(collaboration section, command names)`` pair — the section (see
        below) and the exact-command → bare-agent-id map for the generated
        wrapper/closure commands (the top-level ``command_names`` config).
        ``runtime_context`` (the static
        ``wrapper`` delivery decision — every generated profile command is an
        as-claude wrapper or closure), ``profiles`` (one ``goga-<name>``
        entry per referenced id, each exactly ``{title, command, delegate}``
        — an assistant carrying a non-empty effective env map gets a
        generated closure path as its command) and ``limits`` (only when the
        workflow carries a delegation block).

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
    command_names: dict[str, str] = {}

    for name, (delegate, env, target) in resolved.items():
        command = target
        agent_label = _wrapper_agent_label(target)

        # None and {} both mean "no closure" — the closure materializes on a
        # non-empty effective env map only (an explicitly cleared env is no env).
        if env:
            path = _CLOSURE_BASE / f"{_PROFILE_PREFIX}{name}"
            _write_owner_only(path, _render_closure(env, target))
            command = str(path)

        profiles[f"{_PROFILE_PREFIX}{name}"] = {
            "title": name,
            "command": command,
            "delegate": delegate,
        }
        if agent_label is not None:
            command_names[command] = agent_label

    section: dict[str, object] = {
        "runtime_context": _RUNTIME_CONTEXT,
        "hide_attach_helpers": _HIDE_ATTACH_HELPERS,
        "profiles": profiles,
    }

    if workflow.delegation is not None:
        section["limits"] = {"max_tasks": workflow.delegation.max_tasks}

    return section, command_names


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
            or alone) writes no collaboration profiles — the section head
            (``runtime_context``) still writes.
        workflow: The effective workflow document — the source of each
            referenced assistant's declaration (agent, delegate, env) and of
            the delegation block; ``None`` (with a ``flow`` given or alone)
            writes no collaboration profiles — the section head
            (``runtime_context``) still writes.

    Returns:
        The fixed in-container path of the written file
        (``/home/goga/.afm/config.yaml``), independent of ``AFM_DIR``. The
        content serializes the optional ``client`` block first (the
        ``client.command`` default for stages without a per-stage ``command:``
        override), then the five static launcher fields —
        ``open_browser: false``, ``proxy.enabled: false``, ``prompts_dir:
        /home/goga/pipeline/prompts``, ``add_stage.enabled: false`` (the
        disabled dashboard stage-addition — the stage set presented to the
        engine stays exactly the compiled pipeline), and ``skin_dir:
        /home/goga/.afm/skins/goga`` (the engine's custom skin directory —
        afm serves it wholesale as the active skin while it holds
        ``index.css``; the packaged goga skin is materialized there by the
        run coordination on every launch, and the engine's builtin theme
        names the fallback used only when it does not) — never configurable
        through the project configuration or the CLI — the ``command_names``
        map, written only when non-empty: every generated command — the
        resolved client wrapper and each profile command, wrapper or closure
        alike — labeled with the bare agent id of its underlying
        ``<agent>-as-claude.sh`` wrapper, so the dashboard never falls back
        to the file base name; goga's observer hook registration: a
        ``hooks`` list carrying the single ``goga`` entry (``events: all``,
        the bridge command ``python3 -m goga.pipeline hook``,
        ``inherit_env: true``; ``timeout`` / ``retries`` omitted — the afm
        ``omitempty`` defaults 30 s / 0 — and no ``env`` map); and finally the
        ``collaboration`` section — ALWAYS written, headed by
        ``runtime_context: wrapper`` (the static collaboration execution
        context) and ``hide_attach_helpers: true`` (the dynamic
        attach-helpers dashboard entry point stays hidden — helpers come
        only from the authored workflow plumbing); when both ``flow`` and
        ``workflow`` are given the section also carries one generated
        ``goga-<name>`` profile per flow-referenced id (exactly ``{title,
        command, delegate}``; an assistant carrying a non-empty effective
        env map gets a generated owner-only closure path as its command)
        and ``limits.max_tasks`` only when the workflow carries a
        delegation block.

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
            # "theme": "goga-old",
            "open_browser": False,
            "proxy": {"enabled": False},
            "prompts_dir": _PROMPTS_DIR,
            "add_stage": {"enabled": False},
            "skin_dir": _SKIN_DIR,
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

    if flow is not None and workflow is not None:
        collaboration, profile_command_names = _collaboration_section(agent, flow, workflow)
    else:
        # The section head still writes — the runtime context is a static
        # delivery decision that never depends on the two documents; only the
        # profiles and the task budget are document-derived.
        collaboration = {"runtime_context": _RUNTIME_CONTEXT, "hide_attach_helpers": _HIDE_ATTACH_HELPERS}
        profile_command_names = {}

    # The engine's dashboard label falls back to the file base name; map every
    # generated command to the bare agent id (``claude-as-claude.sh`` → ``claude``).
    command_names = dict(profile_command_names)

    if wrapper is not None:
        client_label = _wrapper_agent_label(wrapper)
        if client_label is not None:
            command_names[wrapper] = client_label

    if command_names:
        content["command_names"] = command_names

    content["collaboration"] = collaboration

    _AFM_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _AFM_CONFIG_PATH.write_text(yaml.safe_dump(content, default_flow_style=False, sort_keys=False))

    if "profiles" in collaboration:
        logger.info(
            "wrote afm collaboration plumbing",
            extra={"profiles": len(collaboration["profiles"]), "has_limits": "limits" in collaboration},
        )

    return _AFM_CONFIG_PATH
