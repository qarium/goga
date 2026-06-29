from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .flow_entry import Source
from .list_flows import list_flows


def run_flow(name: str, project_dir: Path, user_dir: Path) -> int:
    """Run a goga flow by name via the external ``flowmanager`` binary.

    Resolves the flow name to a file via :func:`list_flows`, builds the flow
    file path from the matching entry's source directory, and invokes
    ``flowmanager run <absolute-path>``. The flow's absolute path is always
    passed as a positional argument (never the bare name). The
    ``flowmanager`` binary's exit code is propagated; a missing flow returns a
    non-zero code without invoking the binary; a missing binary is reported
    clearly and returns ``127``.

    Args:
        name: flow name without extension (e.g. ``"deploy"``).
        project_dir: project-level flows directory (typically
            ``<cwd>/.goga/flows/``).
        user_dir: user-level flows directory (typically ``~/.goga/flows/``).

    Returns:
        ``0`` on success; ``1`` when the named flow is not found; ``127`` when
        the ``flowmanager`` binary is missing from ``PATH``; ``126`` when the
        binary cannot be invoked (e.g. present but not executable); otherwise
        the ``flowmanager`` exit code.
    """
    entries = list_flows(project_dir, user_dir)
    match = next((entry for entry in entries if entry.name == name), None)

    if match is None:
        print(f"Error: flow '{name}' not found", file=sys.stderr)
        return 1

    source_dir = project_dir if match.source == Source.PROJECT else user_dir
    # flowmanager resolves the positional arg against its own CWD, so the flow's
    # path must be absolute (see .goga/usages/cooks/flowmanager.md). Resolving
    # here enforces that contract regardless of what callers pass in.
    flow_path = (source_dir / f"{match.name}.yml").resolve()

    try:
        result = subprocess.run(["flowmanager", "run", str(flow_path)], check=False)
        exit_code = result.returncode
    except FileNotFoundError:
        print("Error: flowmanager binary not found in PATH", file=sys.stderr)
        exit_code = 127
    except OSError as e:
        print(f"Error: failed to invoke flowmanager: {e}", file=sys.stderr)
        exit_code = 126

    return exit_code
