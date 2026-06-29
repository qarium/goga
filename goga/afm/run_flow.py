from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_flow(flow_path: Path) -> int:
    """Run a goga flow file via the external ``flowmanager`` binary.

    Thin subprocess-only wrapper: launches ``flowmanager run`` with the given
    absolute pipeline-file path and propagates the subprocess exit code.
    Performs no name resolution or discovery — the caller resolves the path
    (typically :func:`goga.pipeline.run_pipeline`).

    Args:
        flow_path: absolute path to the pipeline file. Passed verbatim to
            ``flowmanager run`` as the positional argument.

    Returns:
        ``0`` on success; ``127`` when the ``flowmanager`` binary is missing
        from ``PATH``; ``126`` when the binary cannot be invoked (e.g. present
        but not executable); otherwise the ``flowmanager`` exit code.
    """
    try:
        result = subprocess.run(["flowmanager", "run", str(flow_path)], check=False)
        return result.returncode
    except FileNotFoundError:
        print("Error: flowmanager binary not found in PATH", file=sys.stderr)
        return 127
    except OSError as e:
        print(f"Error: failed to invoke flowmanager: {e}", file=sys.stderr)
        return 126
