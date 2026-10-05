from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def run_flow(
    flow_path: Path,
    port: int,
    max_parallel: int | None = None,
    env: dict[str, str] | None = None,
) -> int:
    """Run a goga flow file via the external ``afm`` binary.

    Args:
        flow_path: Absolute pipeline file path, passed verbatim to ``afm run``;
            the caller resolves it.
        port: TCP port forwarded to ``afm run --port``; allocated by the caller.
        max_parallel: Optional concurrency cap forwarded as
            ``afm run --max-parallel``; ``None`` omits the flag.
        env: Optional env layer applied over the inherited environment for this
            subprocess only; its values never reach argv, logs, or errors.

    Returns:
        The ``afm`` exit code; ``127`` when the binary is missing from ``PATH``;
        ``126`` when it cannot be invoked or the env layer is rejected.
    """
    cmd = ["afm", "run", "--port", str(port)]
    if max_parallel is not None:
        cmd += ["--max-parallel", str(max_parallel)]
    cmd.append(str(flow_path))

    try:
        if env:
            result = subprocess.run(cmd, check=False, env={**os.environ, **env})
        else:
            result = subprocess.run(cmd, check=False)

        return result.returncode
    except FileNotFoundError:
        print("Error: afm binary not found in PATH", file=sys.stderr)
        return 127
    except (OSError, ValueError):
        # Mirrors run_ralphex's (OSError, ValueError) arm. The ValueError
        # reaches here when the exec rejects the env layer (an illegal
        # environment variable name — e.g. a config-authored pipeline.env key
        # containing "="). The exception text is deliberately NOT
        # interpolated: a rejected layer must not leak any key or value into
        # the message, so the line stays static and content-free.
        print("Error: failed to launch afm", file=sys.stderr)
        return 126
