from __future__ import annotations

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


def run_ralphex(plan: str, options: dict[str, str | int | bool], dry_run: bool) -> int:
    """Run the external ``ralphex`` binary for the given build plan.

    Thin subprocess-only wrapper: assembles the ralphex command from the
    resolved options, optionally prints it on a dry run, otherwise checks the
    binary is on PATH and invokes it via ``subprocess.call`` — inheriting the
    process environment so the build env delivered through the container
    env-file by the host launcher reaches ralphex. Propagates the subprocess
    exit code.

    Performs no config generation (.ralphex/config), option resolution
    (CLI > ProjectConfig > omit), or agent-wrapper resolution — those live in
    goga/build.

    Args:
        plan: Path to the plan file (resolved by the caller). Passed verbatim
            to ralphex as the positional argument.
        options: Resolved ralphex options (precedence already applied by the
            caller). Each key maps to exactly one ralphex CLI flag.
        dry_run: When True, print the assembled command to sys.stderr and
            return 0 without launching.

    Returns:
        ``0`` on success or on a dry run; ``1`` when the ``ralphex`` binary is
        missing from ``PATH``; otherwise ralphex's own exit code.
    """
    cmd = _build_command(plan, options)

    if dry_run:
        print(shlex.join(cmd), file=sys.stderr)
        return 0

    if not shutil.which("ralphex"):
        print("Error: ralphex binary not found in PATH", file=sys.stderr)
        return 1

    return subprocess.call(cmd)
