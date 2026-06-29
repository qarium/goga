# Running AI-flow scenarios via flowmanager

## Tool

**flowmanager** is an external CLI tool (Go binary) that orchestrates multi-stage AI-flow scenarios.

Installation: an external binary placed on `PATH` (outside the `goga` repository). Verify availability with `which flowmanager`.

**IMPORTANT** — `flowmanager` is an external tool, distinct from `goga`. It is modified and developed in a separate repository; `goga` only integrates with its CLI contract.

## CLI contract (current)

`flowmanager` runs as a top-level command with no global configuration options (only `--help`).

### Commands

| Command                  | Purpose                                                            |
|--------------------------|--------------------------------------------------------------------|
| `flowmanager init`       | Interactively create `flow.yaml`                                   |
| `flowmanager list`       | List flow files from `.flowManager/flows/` relative to CWD         |
| `flowmanager run`        | Run a flow (or resume the most recent run)                         |
| `flowmanager check`      | Display the status of the last run                                 |
| `flowmanager approve`    | Approve a stage plan (`awaiting_approval` → `ready`)               |
| `flowmanager retry`      | Retry a failed stage (`failed` → `pending`)                        |
| `flowmanager revise`     | Submit feedback to revise a stage plan                             |

### Key command — `run`

```
flowmanager run [flow.yaml] [flags]
```

- Accepts a **path to the flow file** as a positional argument.
- If the path is omitted, it searches `.flowManager/flows/` relative to CWD and/or resumes the most recent run.
- **Accepts an absolute path**, which allows running pipeline files from any directory (including `~/.goga/pipelines/`) without copying them into `.flowManager/flows/`.

Optional `run` flags:

- `--idle-timeout duration` — agent idle timeout
- `--max-parallel int` — maximum number of parallel stages (0 = no limit)
- `--port int` — dashboard port (0 = read from config)

### Key command — `list`

```
flowmanager list [flags]
```

- Lists flows **only from `.flowManager/flows/`** relative to the current working directory.
- **There is no flag to override the directory.** As a result, `flowmanager list` cannot see pipelines stored in `~/.goga/pipelines/` directly.

## Integration with goga

`goga` stores pipeline files centrally in `~/.goga/pipelines/` (the user's home directory). This directory is **unlinked** from `.flowManager/flows/` (the runner's working directory within a given project) — they serve different roles:

- `~/.goga/pipelines/` — the single storage location for pipeline files owned by `goga`; populated by the `goga connect` command.
- `.flowManager/flows/` — the `flowmanager` runner's working directory within a specific project; used by `flowmanager list` / `flowmanager run` when invoked without arguments.

### Invocation pattern from `goga pipeline <name>`

To run a pipeline stored in `~/.goga/pipelines/` without copying it into the project's `.flowManager/flows/`, `goga pipeline <name>` passes an **absolute path**:

```python
import subprocess
from pathlib import Path

pipeline_path = Path.home() / ".goga" / "pipelines" / f"{name}.yml"
result = subprocess.run(
    ["flowmanager", "run", str(pipeline_path)],
    check=False,
)
```

- The path is passed as a positional argument to `flowmanager run`.
- `flowmanager` reads the pipeline file at the specified absolute path, regardless of CWD.

### Handling subprocess errors

| Case                                                       | `subprocess.run` behavior             | Requirement for `goga pipeline <name>`              |
|------------------------------------------------------------|---------------------------------------|------------------------------------------------------|
| `flowmanager` binary not found on `PATH`                   | `FileNotFoundError`                   | Catch it, emit a clear message, exit ≠ 0             |
| `flowmanager` exits with a non-zero code                   | `result.returncode != 0`              | Propagate the return code, or emit diagnostics       |
| Pipeline file `<name>.yml` missing in `~/.goga/pipelines/` | — (validated before the subprocess)   | Emit a clear error, exit ≠ 0, skip the subprocess    |

**IMPORTANT** — `FileNotFoundError` must be caught explicitly. Crashing with a raw exception when `flowmanager` is absent is an anti-pattern.

## Anti-patterns

- Do not pass a pipeline name as an identifier to `flowmanager run` (e.g., `flowmanager run my-pipeline`). `flowmanager` interprets the argument as a path, not as a name — pass the file path instead.
- Do not copy pipelines from `~/.goga/pipelines/` into `.flowManager/flows/` solely to run them. An absolute path resolves the task without duplication.
- Do not rely on `flowmanager list` seeing pipelines in `~/.goga/pipelines/` — it exposes no directory-override flag. `goga pipeline` (discovery mode) must read `~/.goga/pipelines/` directly, rather than via `flowmanager list`.
- Do not modify the external `flowmanager` to accommodate the integration. It is developed independently; `goga` adapts to its CLI contract.
