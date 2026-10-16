"""The ``write_role_env_wrappers`` routine — the per-role sh closures carrying env layers."""

from __future__ import annotations

import logging
import re
import shlex
from pathlib import Path

from ..agents import resolve_wrapper_path
from .run_settings import RunSettings

logger = logging.getLogger(__name__)

# The container-local base directory of the generated closures — never under
# /workspace. A module constant so the tests (and only they) can relocate it.
_WRAPPER_BASE = Path("/tmp/goga-build-env")

# The engine-variable keys that never enter a generated closure: launch
# mechanics belong to the launcher, so a role-env or CLI entry colliding with
# one of them is dropped silently — the inherited launch value stands, with no
# warning.
_ENGINE_ENV_KEYS = frozenset(
    {
        "AFM_DIR",
        "AFM_DOCKER_FILE_ROOTS",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "GOGA_PROFILE",
        "GOGA_WORKFLOW",
        "GOGA_HOME_PROFILES",
        "GOGA_EXTRA_ENV",
    },
)

# A legal environment variable name per POSIX — the only shape ``export
# KEY=value`` in a generated sh closure accepts.
_LEGAL_ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# The fixed role iteration order and, per role, the remedy line of the
# missing-agent error.
_ROLES = ("tasks", "review", "additional")

_ROLE_AGENT_REMEDY = {
    "tasks": "set build.agent",
    "review": "set build.agent or build.review.agent",
    "additional": "set build.review.additional.agent",
}


def _role_agent(settings: RunSettings, role: str) -> str | None:
    """The executor agent of one role.

    Args:
        settings: The resolved run plan of the run.
        role: The role identity — exactly ``tasks``, ``review``, or
            ``additional``.

    Returns:
        The role's settings agent (already inheritance-resolved), or None
        when the role carries no agent.
    """
    if role == "tasks":
        return settings.tasks.agent

    if role == "review":
        return settings.review.agent

    return settings.review.additional.agent


def _role_env(settings: RunSettings, role: str) -> dict[str, str]:
    """The env layer of one role.

    Args:
        settings: The resolved run plan of the run.
        role: The role identity — exactly ``tasks``, ``review``, or
            ``additional``.

    Returns:
        The role's own env layer, verbatim — never another role's.
    """
    if role == "tasks":
        return settings.tasks.env

    if role == "review":
        return settings.review.env

    return settings.review.additional.env


def _compose_layer(role_env: dict[str, str], cli_entries: dict[str, str]) -> dict[str, str]:
    """Compose one role's closure layer: role env overlaid with the CLI entries, engine keys dropped.

    Args:
        role_env: The role's own env layer — the base.
        cli_entries: The decoded CLI entries payload — applied on top, so the
            CLI wins per key.

    Returns:
        The composed layer with every engine-variable key dropped silently.
    """
    merged = {**role_env, **cli_entries}

    return {key: value for key, value in merged.items() if key not in _ENGINE_ENV_KEYS}


def _render_script(layer: dict[str, str], wrapper: str) -> str:
    """Render one role's sh closure: export the layer, then exec the wrapper.

    Args:
        layer: The composed env layer of the role — every key already
            validated as a legal environment variable name.
        wrapper: The resolved in-container wrapper path of the role agent —
            the exec target.

    Returns:
        The script text: the shebang, one ``export`` line per entry (values
        shell-quoted), and the exec line forwarding ``"$@"``.
    """
    exports = "".join(f"export {key}={shlex.quote(value)}\n" for key, value in layer.items())

    return f'#!/bin/sh\n{exports}exec {wrapper} "$@"\n'


def write_role_env_wrappers(settings: RunSettings, cli_entries: dict[str, str]) -> dict[str, Path]:
    """Generate the per-role closure wrappers every build pass executor runs through.

    Each wrapper exports the role's env layer with the decoded CLI entries
    applied on top (the CLI wins per key, engine-variable keys dropped
    silently), then execs the role agent's resolved wrapper — so the same
    agent can carry different env per role and the layers never cross.

    Args:
        settings: The resolved run plan — the agents (already
            inheritance-resolved) and the env layers of the three roles.
        cli_entries: The decoded CLI entries payload (the
            ``decode_extra_env`` result) — one decode feeds every role.

    Returns:
        The role-to-wrapper-path mapping; the keys are exactly ``tasks``,
        ``review``, and ``additional``.

    Raises:
        ValueError: When a role carries no agent (naming the role and its
            remedy), or when a composed layer key is not a legal environment
            variable name (naming the role and the key) — both raised before
            any script file is written, so no pass can launch on a partial
            wrapper set.
    """
    base = _WRAPPER_BASE
    base.mkdir(parents=True, exist_ok=True)

    closures: dict[str, tuple[Path, str]] = {}

    for role in _ROLES:
        agent = _role_agent(settings, role)

        if agent is None:
            raise ValueError(f"no agent resolved for the {role} role: {_ROLE_AGENT_REMEDY[role]}")

        wrapper = resolve_wrapper_path(agent)
        layer = _compose_layer(_role_env(settings, role), cli_entries)

        for key in layer:
            if _LEGAL_ENV_NAME_PATTERN.fullmatch(key) is None:
                raise ValueError(f"invalid environment variable name in the {role} role layer: {key!r}")

        closures[role] = (base / f"{role}.sh", _render_script(layer, wrapper))

    for path, script in closures.values():
        path.write_text(script)
        path.chmod(0o755)

    paths = {role: path for role, (path, _script) in closures.items()}

    logger.info("wrote role env wrappers", extra={"paths": [str(path) for path in paths.values()]})

    return paths
