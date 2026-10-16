"""The ``write_role_env_wrappers`` routine — the per-role sh closures carrying env layers."""

from __future__ import annotations

import logging
import os
import re
import shlex
from pathlib import Path

from ..agents import resolve_wrapper_path
from .run_settings import RunSettings

logger = logging.getLogger(__name__)

# The container-local base directory of the generated closures — never under
# /workspace. A module constant so the tests (and only they) can relocate it.
# Each build run owns a per-run subdirectory (PID-keyed): concurrent builds
# in one container — parallel pipeline stages each running a nested build —
# never share or clobber each other's closures.
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

# The fixed role iteration order — each entry carries the role's settings
# accessors and the remedy line of the missing-agent error.
_ROLES = (
    ("tasks", lambda settings: settings.tasks.agent, lambda settings: settings.tasks.env, "set build.agent"),
    (
        "review",
        lambda settings: settings.review.agent,
        lambda settings: settings.review.env,
        "set build.agent or build.review.agent",
    ),
    (
        "additional",
        lambda settings: settings.review.additional.agent,
        lambda settings: settings.review.additional.env,
        "set build.review.additional.agent",
    ),
)


def _run_base() -> Path:
    """The per-run wrapper directory of the current build process.

    Returns:
        The PID-keyed subdirectory under the relocatable base — unique among
        live processes, so concurrent builds never interleave wrapper writes.
    """
    return _WRAPPER_BASE / f"run-{os.getpid()}"


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
        shell-quoted), and the exec line (the wrapper shell-quoted) forwarding
        ``"$@"``.
    """
    exports = "".join(f"export {key}={shlex.quote(value)}\n" for key, value in layer.items())

    return f'#!/bin/sh\n{exports}exec {shlex.quote(wrapper)} "$@"\n'


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
        ``review``, and ``additional``. The closures live in a per-run
        PID-keyed subdirectory of the base, owner-accessible only (0o700), so
        concurrent builds in one container never collide and the env layers
        stay invisible to other container users.

    Raises:
        ValueError: When a role carries no agent (naming the role and its
            remedy), or when a composed layer key is not a legal environment
            variable name (naming the role and the key) — both raised before
            any script file is written, so no pass can launch on a partial
            wrapper set.
    """
    base = _run_base()
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    # mkdir(exist_ok=True) keeps the mode of an existing directory — pin it
    # so a pre-existing base never widens the closure visibility.
    base.chmod(0o700)

    closures: dict[str, tuple[Path, str]] = {}

    for role, agent_of, env_of, remedy in _ROLES:
        agent = agent_of(settings)

        if agent is None:
            raise ValueError(f"no agent resolved for the {role} role: {remedy}")

        wrapper = resolve_wrapper_path(agent)
        layer = _compose_layer(env_of(settings), cli_entries)

        for key in layer:
            if _LEGAL_ENV_NAME_PATTERN.fullmatch(key) is None:
                raise ValueError(f"invalid environment variable name in the {role} role layer: {key!r}")

        closures[role] = (base / f"{role}.sh", _render_script(layer, wrapper))

    for path, script in closures.values():
        _write_owner_only(path, script)

    paths = {role: path for role, (path, _script) in closures.items()}

    logger.info("wrote role env wrappers", extra={"paths": [str(path) for path in paths.values()]})

    return paths
