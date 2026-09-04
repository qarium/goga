# Usages — API

The facade of the domain package **`goga.usages`** — a re-export facade embedding `sync` and `status` (with the status result types) so consumers import a single entry point. It owns no behavior — the logic lives in the child cells `goga.usages.sync` and `goga.usages.status`.

The signatures below are the CODEMANIFEST contract of the cells.

## Sync

```python
sync(force: bool = False, group: str | None = None, dep: str | None = None) -> int
clean_usages_dir(usages_root: Path) -> int
clone_repository(git: str, ref: str | None) -> Path
deploy_usages(source_repo: Path, target_dir: Path, root: str | None = None) -> int
```

`sync` materializes and refreshes the usage files of every declared dependency (or one `group`/`dep` slice) into `.goga/usages/` — clone each remote at its `ref`, discover `.usages` folders under `root`, copy the files; `force` overwrites local modifications. Returns the exit code. The helpers behind it: the idempotent wipe of the target tree, the clone, and the deployment of one dependency's files.

## Status

```python
status(group: str | None = None, dep: str | None = None) -> UsageStatusReport
hash_tree(root: Path) -> dict[str, str]
compute_dep_status(group: str, dep: str, depcfg: DepConfig, target: Path) -> DepStatus
```

`status` checks the synchronized files against each dependency's current remote state — clone at the remote tip, hash both trees, compare — and returns the report. The helpers: the tree hashing and one dependency's comparison.

## The result types

```python
UsageStatusReport(deps: list[DepStatus])
DepStatus(group: str, dep: str, state: UsageState, entries: list[EntryStatus], error: str | None = None)
EntryStatus(path: str, kind: EntryKind, change: EntryChange)
```

One `DepStatus` per dependency: its `state` (`UsageState`), its per-entry statuses, and an `error` when the remote could not be reached. Each `EntryStatus` carries the file's `path`, its `kind` (local/remote), and the `change` class.

## Example

```python
from goga.usages import status, sync

sync()                                  # materialize every declared dependency
report = status()
for dep in report.deps:
    print(dep.group, dep.dep, dep.state)
```
