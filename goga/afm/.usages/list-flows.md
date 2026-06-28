# List Flows — goga/afm

## Overview

`list_flows` discovers flow files across two source directories and returns them
as `FlowEntry`-s. Use this when you need to enumerate available flows
(for CLI output, validation, or selection UIs).

## Source Directories

| Parameter      | Typical path            | Meaning                                              |
|----------------|-------------------------|------------------------------------------------------|
| `project_dir`  | `<cwd>/.goga/flows/`    | Project-level flows, user-authored. Priority source. |
| `user_dir`     | `~/.goga/flows/`        | User-level flows, installed by `goga connect`.       |

When a flow name exists in both, the project source wins.

## Usage

```python
from pathlib import Path
from goga.afm import FlowEntry, list_flows

project_dir = Path.cwd() / ".goga" / "flows"
user_dir = Path.home() / ".goga" / "flows"

entries: list[FlowEntry] = list_flows(project_dir, user_dir)
for entry in entries:
    print(f"{entry.name} ({entry.source.value})")
```

## Parameters

- `project_dir: Path` — project flows directory (scanned flat, non-recursive)
- `user_dir: Path` — user flows directory (scanned flat, non-recursive)

Returns `list[FlowEntry]` — one entry per unique name; duplicates resolved toward project source.

## Side Effects

- Reads the filesystem only (no writes).

## Preconditions

- Flow files must reside at the top level of a source directory (subdirectories are not scanned).
- Flow file names must use the `.yml` extension; the returned `FlowEntry.name` omits it.

## Anti-patterns

- Do not scan subdirectories — only flat `*.yml` is supported.
- Do not assume flows from `.flowManager/flows/` will appear — that directory is `flowmanager`'s own and unrelated.
