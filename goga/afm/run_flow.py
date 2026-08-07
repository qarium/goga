from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_flow(flow_path: Path, port: int, max_parallel: int | None = None) -> int:
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

    Returns:
        ``0`` on success; ``127`` when the ``afm`` binary is missing
        from ``PATH``; ``126`` when the binary cannot be invoked (e.g. present
        but not executable); otherwise the ``afm`` exit code.
    """
    cmd = ["afm", "run", "--port", str(port)]
    if max_parallel is not None:
        cmd += ["--max-parallel", str(max_parallel)]
    cmd.append(str(flow_path))

    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except FileNotFoundError:
        print("Error: afm binary not found in PATH", file=sys.stderr)
        return 127
    except OSError as e:
        print(f"Error: failed to invoke afm: {e}", file=sys.stderr)
        return 126
