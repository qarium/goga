# Flows run Command — goga/commands/flow

## Overview

`goga flows run <name>` runs a flow by name via the external `flowmanager` binary.
The `.yml` extension is added internally during path resolution — pass the bare name only.

## Usage

```bash
goga flows run deploy
```

## Argument

- `name` (positional, required) — flow name without extension. The command resolves
  the path to `<source_dir>/<name>.yml` and passes the absolute path to `flowmanager run`.

## Path Resolution

The flow file is resolved across two source directories with project priority:

| Directory     | Path                   |
|---------------|------------------------|
| `project_dir` | `<cwd>/.goga/flows/`   |
| `user_dir`    | `~/.goga/flows/`       |

If the name exists in both, the project source wins.

## Exit Codes

| Exit code | Condition                                                      |
|-----------|----------------------------------------------------------------|
| 0         | flowmanager ran the flow successfully                          |
| non-zero  | flow not found in either source                                |
| non-zero  | `flowmanager` binary not in PATH (clear message, no traceback) |
| non-zero  | flowmanager itself returned a non-zero exit code               |

## Preconditions

- The `flowmanager` binary must be in `PATH`.
- The flow name must exist in one of the two source directories.

## Side Effects

Inherits all side effects of the invoked flow (the flow may create files, run commands, etc.).

## Anti-patterns

- Do not pass a file path or a name with `.yml` — pass the bare flow name.
- Do not copy flows into `.flowManager/flows/` just to run them — `run` passes the absolute path directly.
