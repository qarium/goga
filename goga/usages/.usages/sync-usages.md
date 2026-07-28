# Usages sync — goga/usages

## Domain

Programmatic, config-driven synchronization of cell-level usages from declared git
dependencies into `.goga/usages/<group>/<dep>/`. Target audience: the `goga usages sync`
command and any caller running usages synchronization programmatically.

## Facade

```python
from goga.usages import sync

exit_code = sync(force=False)
```

## Configuration contract

`sync` reads the `usages` section of `.goga/config.yml` via `load_project_config`:

```yaml
usages:
  libs:
    click:
      git: https://github.com/pallets/click.git
      ref: main
      root: docs           # optional — subpath inside the repo to walk from
```

- Each `<group>/<dep>` declares a `git` URL (required) and an optional `ref`
  (branch / tag / commit; absent → default branch).
- Each `<group>/<dep>` may declare an optional `root` — a subpath inside the cloned
  repository from which `.usages` folders are discovered and against which destination
  paths are computed. Absent (or an empty string `root: ""`) → walk from the repository
  root. `root` is structurally validated at the config boundary (no `..`, no absolute paths).
- When the `usages` section is absent → `sync` is a no-op (exit 0).

## On-disk result

For each declared dep, files are written under `.goga/usages/<group>/<dep>/`. For every
`.usages` folder found under the dep's `root`, its contents are copied to the path of its
**parent relative to `root`**, with the `.usages` segment dropped. Intermediate non-cell
directories are preserved verbatim. There is no smoothing: placement is deterministic.

With `root: folder`:

- `folder/cell_1/cell_2/.usages` → `.goga/usages/<group>/<dep>/cell_1/cell_2/`
- `folder/subfolder/cell_1/cell_2/.usages` → `.goga/usages/<group>/<dep>/subfolder/cell_1/cell_2/`
- `folder/subfolder/cell_1/another_folder/cell_2/.usages` → `.goga/usages/<group>/<dep>/subfolder/cell_1/another_folder/cell_2/`

A `.usages` folder directly at the `root` copies into the dep root (empty relative path).

A repository containing a single `.usages` folder is placed at its `root`-relative path —
at the dep root only when it sits directly at the `root`. Placement is deterministic: no
flattening is applied. Declare an explicit `root` to control where a single `.usages`
folder lands.

VCS folders (`.git`/`.hg`/`.svn`) are excluded from discovery and copying. Symlinks are
copied verbatim (not dereferenced).

If `root` does not resolve to an existing directory inside the clone (missing or a file),
the dep fails with an explicit error rather than producing an empty result.

## Modes

- Incremental (default, `force=False`): a dep whose target dir already exists is skipped.
  Changing `git`/`ref`/`root` in config does NOT re-sync an existing dep.
- Force (`force=True`): every subdirectory of `.goga/usages/` except `cooks` is removed
  (root `*.md` files kept), then all declared deps are re-synced.

## Exit codes

- `0` — success (including "nothing to sync").
- `1` — at least one dep failed (best-effort: other deps still attempted).

## Constraints for consumers

- Call `sync` only from a directory containing `.goga/config.yml`.
- `--force` is the only mechanism to refresh an already-synced dep.
- `cooks/` and root `*.md` in `.goga/usages/` are never touched.
