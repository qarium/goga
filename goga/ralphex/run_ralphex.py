from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys

# Fixed option -> ralphex CLI flag mapping. Dictated by the run_ralphex
# contract (see the `options` annotation), NOT by the ralphex practice —
# changing the flag set is a CODEMANIFEST change, not an implementation one.
_BOOL_FLAGS: tuple[tuple[str, str], ...] = (
    ("worktree", "--worktree"),
    ("skip_finalize", "--skip-finalize"),
    ("review", "--review"),
    ("tasks_only", "--tasks-only"),
)
_SCALAR_FLAGS: tuple[tuple[str, str], ...] = (
    ("session_timeout", "--session-timeout"),
    ("idle_timeout", "--idle-timeout"),
    ("wait", "--wait"),
    ("max_iterations", "--max-iterations"),
    ("review_patience", "--review-patience"),
)


def _build_command(plan: str, options: dict[str, str | int | bool]) -> list[str]:
    """Assemble the ralphex argv from the resolved options.

    The option precedence (CLI > ProjectConfig > omit) has already been applied
    by the caller (goga/build); this helper performs no resolution — it only
    maps each resolved option key to exactly one ralphex CLI flag per the fixed
    mapping in the run_ralphex contract. A bool key that is True emits a bare
    flag (False or absent -> omit); a scalar key emits ``--<flag> <value>``
    unless the value is None, an empty string, or 0.

    Args:
        plan: Path to the plan file, passed to ralphex positionally.
        options: Resolved ralphex options (precedence already applied by the
            caller).

    Returns:
        The full ralphex argv, always starting with
        ``["ralphex", plan, "--config-dir", ".ralphex/"]`` followed by the
        mapped flags in fixed order.
    """
    cmd: list[str] = ["ralphex", plan, "--config-dir", ".ralphex/"]

    for key, flag in _BOOL_FLAGS:
        if options.get(key) is True:
            cmd.append(flag)

    for key, flag in _SCALAR_FLAGS:
        value = options.get(key)
        if value not in (None, "", 0):
            cmd.extend([flag, str(value)])

    return cmd


def run_ralphex(
    plan: str,
    options: dict[str, str | int | bool],
    dry_run: bool,
    env: dict[str, str] | None = None,
) -> int:
    """Run the external ``ralphex`` binary for the given build plan.

    Thin subprocess-only wrapper: assembles the ralphex command from the
    resolved options, optionally prints it on a dry run, otherwise checks the
    binary is on PATH and invokes it via ``subprocess.call`` — inheriting the
    process environment so the build env delivered through the container
    env-file by the host launcher reaches ralphex. A non-empty ``env`` layer
    is applied on top of that inherited environment for this subprocess only.
    Propagates the subprocess exit code.

    Performs no config generation (.ralphex/config), option resolution
    (CLI > ProjectConfig > omit), or agent-wrapper resolution — those live in
    goga/build. The subprocess environment is composed from ``os.environ``
    plus ``env`` and no other source.

    Args:
        plan: Path to the plan file (resolved by the caller). Passed verbatim
            to ralphex as the positional argument.
        options: Resolved ralphex options (precedence already applied by the
            caller). Each key maps to exactly one ralphex CLI flag.
        dry_run: When True, print the assembled command to sys.stderr and
            return 0 without launching. The env layer is never printed.
        env: Optional environment layer ({str: str}) for this subprocess only.
            Keys override same-named inherited variables; every other
            inherited variable passes through unchanged. ``None`` or ``{}``
            means pure inheritance (``subprocess.call`` without an ``env``
            kwarg). The layer is secret-safe: it never reaches the argv, the
            logs, or the dry-run output, and never mutates the parent's
            ``os.environ``.

    Returns:
        ``0`` on success or on a dry run; ``1`` when the ``ralphex`` binary is
        missing from ``PATH`` — including when an ``env`` layer's ``PATH``
        override hides it from the exec — or when the launch itself is rejected
        before the exec (a ``PATH`` override resolving a non-executable or
        non-directory ralphex, an oversized layer, or an illegal environment
        variable name); otherwise ralphex's own exit code.
    """
    cmd = _build_command(plan, options)

    if dry_run:
        print(shlex.join(cmd), file=sys.stderr)
        return 0

    if not shutil.which("ralphex"):
        print("Error: ralphex binary not found in PATH", file=sys.stderr)
        return 1

    try:
        if env:
            return subprocess.call(cmd, env={**os.environ, **env})

        return subprocess.call(cmd)
    except FileNotFoundError:
        # An env layer that overrides PATH can hide the binary from the exec
        # even though the guard above resolved it in the inherited PATH — the
        # same clean message and exit code, not a traceback.
        print("Error: ralphex binary not found in PATH", file=sys.stderr)
        return 1
    except (OSError, ValueError) as e:
        # The sibling PATH-override failures (the overlaid PATH resolves a
        # ralphex that is present but not executable, or names a non-directory
        # component, or the layer is too large to exec) and an env layer key
        # that is not a legal environment variable name (e.g. contains "=")
        # are all rejected by the exec before the launch — a clean message
        # and exit 1, not a traceback escaping to the caller.
        print(f"Error: failed to invoke ralphex: {e}", file=sys.stderr)
        return 1
