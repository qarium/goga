# Usages — Configuration

The usages domain reads one optional section of `.goga/config.yml` — `usages`, the git dependencies whose cell-level `.usages/` files are synced by [`goga usages sync`](cli.md) and checked by [`goga usages status`](cli.md).

```yaml
usages:
  cooks:                      # group — a subdirectory of .goga/usages/
    goga:                     # dependency — a subdirectory of the group
      git: https://github.com/qarium/goga.git
      ref: 1.3.x              # optional — branch, tag, or commit
      root: docs              # optional — subpath to discover .usages from
```

A two-level mapping: `<group>` → `<dep>` → fields.

| Field | Type | Required | Description |
|---|---|---|---|
| `usages.<group>` | mapping | Yes when `usages` present | Group bucket. The key becomes a top-level subdirectory of `.goga/usages/`. Validated as a path segment (no empty / `.` / `..` / `/` / `\`) |
| `usages.<group>.<dep>` | mapping | Yes when `<group>` present | Dependency entry. The key becomes a subdirectory under the group. Same path-segment validation |
| `usages.<group>.<dep>.git` | `string` | Yes | Git URL of the source repository. Must be non-empty |
| `usages.<group>.<dep>.ref` | `string` | No | Git ref — branch, tag, or commit. `None` (omitted) clones the default branch |
| `usages.<group>.<dep>.root` | `string` | No | Subpath inside the clone to discover `.usages` folders from. Absent (or an empty string) → clone root. Must be relative; no `..` or absolute paths |

`usages` defaults to `None` (absent), which makes `goga usages sync` a no-op (exit 0); an empty mapping is `{}`.

The general file location, loading rules, and the shared example live in [Project Configuration](../../configuration/project.md).
