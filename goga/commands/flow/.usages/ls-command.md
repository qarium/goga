# Flows ls Command — goga/commands/flow

## Overview

`goga flows ls` lists flow names discovered across two source directories:
the project-level `.goga/flows/` (relative to CWD) and the user-level `~/.goga/flows/`.
It is a read-only command and does not invoke `flowmanager`.

## Usage

```bash
goga flows ls
```

Example output (project flows are annotated with `(project)`):

```
deploy (project)
build
test
```

## Behavior

- Scans flat `*.yml` at the top level of each source directory (subdirectories are ignored).
- Project source wins on name conflicts — the user-level entry with the same name is hidden.
- Missing source directories are treated as empty (no error).

## Source Directory Resolution

| Directory     | Path                   |
|---------------|------------------------|
| `project_dir` | `<cwd>/.goga/flows/`   |
| `user_dir`    | `~/.goga/flows/`       |

## Side Effects

- Reads the filesystem only (no writes).

## Anti-patterns

- Do not expect flows from `.flowManager/flows/` to appear — that is `flowmanager`'s own directory and unrelated.
- Do not expect subdirectory flows to be listed — only flat `*.yml` is scanned.
