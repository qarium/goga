# Pipeline Command — goga/commands/pipeline

## Overview

`goga pipeline [<name>]` is a single command that replaces the former
two-subcommand surface (`goga flow ls`, `goga flow run <name>`). Its behavior
depends on whether `name` is given:

- **Without `name` (discovery mode):** prints the `Available pipelines:` header
  followed by the list of available pipelines discovered across the project and
  user pipeline directories. Read-only; does not invoke `flowmanager`.
- **With `name` (run mode):** runs the named pipeline via the external
  `flowmanager` binary. The `.yml` extension is added internally during path
  resolution — pass the bare name only.

## Usage — discovery mode (no argument)

```bash
goga pipeline
```

Example output (project pipelines are annotated with `(project)`):

```
Available pipelines:
  deploy (project)
  build
  test
```

The header is always printed, even when the list is empty.

## Usage — run mode (with name)

```bash
goga pipeline deploy
```

## Argument

- `name` (positional, optional) — pipeline name without extension. When absent
  → discovery mode. When provided → run mode.

## Source Directory Resolution

| Directory     | Path                   |
|---------------|------------------------|
| `project_dir` | `<cwd>/.goga/pipelines/`   |
| `user_dir`    | `~/.goga/pipelines/`       |

If the name exists in both sources, the project source wins.

## Exit Codes (run mode)

| Exit code | Condition                                                      |
|-----------|----------------------------------------------------------------|
| 0         | flowmanager ran the pipeline successfully                      |
| non-zero  | pipeline not found in either source                            |
| 127       | `flowmanager` binary not in PATH (propagated from `run_pipeline` → `run_flow`) |
| non-zero  | flowmanager itself returned a non-zero exit code (propagated)  |

## Exit Codes (discovery mode)

| Exit code | Condition |
|-----------|-----------|
| 0         | always (even if list is empty) |

## Side Effects

- Discovery mode: reads the filesystem only (no writes).
- Run mode: inherits all side effects of the invoked pipeline.

## Preconditions

- (Run mode) The `flowmanager` binary must be in `PATH`.
- (Run mode) The pipeline name must exist in one of the two source directories.

## Anti-patterns

- Do not expect `ls` or `run` subcommands — this is a single `goga pipeline` command.
- Do not expect auto-`--help` when no name is given — the discovery mode output (`Available pipelines:` + list) is shown instead.
- Do not pass a file path or a name with `.yml` in run mode — pass the bare pipeline name only.
- Do not copy pipelines into `.flowManager/flows/` just to run them — run mode resolves and passes the absolute path directly.
