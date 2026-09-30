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

    Thin subprocess-only wrapper: launches ``afm run`` with the given absolute
    pipeline-file path and binds its dashboard to ``port``, optionally capping
    concurrency, and propagates the subprocess exit code. Performs no name
    resolution, path resolution, or port allocation — the caller resolves the
    path and allocates the port (typically
    :func:`goga.pipeline.run_pipeline` and
    :func:`goga.commands.pipeline.run_pipeline_container`).

    Args:
        flow_path: absolute path to the pipeline file. Passed verbatim to
            ``afm run`` as the positional argument.
        port: TCP port forwarded to ``afm run --port``. Allocated by the
            caller.
        max_parallel: optional cap on concurrently executing stages. When not
            ``None``, forwarded as ``afm run --max-parallel <max_parallel>``
            (inserted after ``--port``, before the positional path). When
            ``None`` (default), the ``--max-parallel`` flag is OMITTED and afm
            applies its own default — backward compatible. ``None`` is never
            substituted with a concrete value (e.g. ``0``).
        env: optional environment layer applied on top of the inherited
            process environment for this subprocess only. Composed by the
            caller (the run coordination) as the effective task env layer with
            the CLI entries applied above it. ``None`` or an empty mapping
            means pure inheritance (the subprocess is launched without an
            ``env`` kwarg). The layer is secret-safe: its values never reach
            the argv, the logs, or any error message, and the caller's
            ``os.environ`` is never mutated.

    Returns:
        ``0`` on success; ``127`` when the ``afm`` binary is missing
        from ``PATH``; ``126`` when the binary cannot be invoked (e.g. present
        but not executable) or the environment layer is rejected by the exec
        (e.g. an illegal variable name inside the layer); otherwise the
        ``afm`` exit code.
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
