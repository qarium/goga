# Run Flow — goga/afm

## Overview

`run_flow` resolves a flow name to a file path across the two source directories,
then invokes the external `flowmanager` binary to run it. Use this to launch a flow by name.

## Usage

```python
from pathlib import Path
from goga.afm import run_flow

project_dir = Path.cwd() / ".goga" / "flows"
user_dir = Path.home() / ".goga" / "flows"

exit_code = run_flow("deploy", project_dir, user_dir)
```

## Parameters

- `name: str` — flow name without extension (the `.yml` suffix is added internally during path resolution)
- `project_dir: Path` — project flows directory (same meaning as in `list_flows`)
- `user_dir: Path` — user flows directory (same meaning as in `list_flows`)

## Return Values

| Exit code | Condition                                                      |
|-----------|----------------------------------------------------------------|
| 0         | flowmanager ran the flow successfully                          |
| non-zero  | flow not found in either source                                |
| non-zero  | `flowmanager` binary not in PATH (clear message, no traceback) |
| non-zero  | flowmanager itself returned a non-zero exit code               |

## Path Resolution

The flow file is resolved via `list_flows` semantics — the project source wins on name conflicts.
The absolute path is then passed to `flowmanager run` as a positional argument.

## Side Effects

`run_flow` invokes `flowmanager` as a subprocess and inherits its side effects
(the flow may create files, run commands, etc., as defined by the flow file itself).

## Preconditions

- The `flowmanager` binary must be in `PATH` (invoke via subprocess; missing binary raises `FileNotFoundError`).
- The flow name must exist in one of the two source directories (after project-priority resolution).

## Anti-patterns

- Do not pass a bare flow name to `flowmanager` directly — `run_flow` resolves the path and adds the extension.
- Do not copy flow files into `.flowManager/flows/` just to run them — `run_flow` passes the absolute path directly.
