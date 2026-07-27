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
```

- Each `<group>/<dep>` declares a `git` URL (required) and an optional `ref`
  (branch / tag / commit; absent → default branch).
- When the `usages` section is absent → `sync` is a no-op (exit 0).

## On-disk result

For each declared dep, files are written under `.goga/usages/<group>/<dep>/`:

- One `.usages` in the repo → its contents land at the dep root.
- Multiple `.usages` → each is placed at its repo-relative path (the `.usages` segment
  is dropped; intermediate non-cell directories are preserved).

## Modes

- Incremental (default, `force=False`): a dep whose target dir already exists is skipped.
  Changing `git`/`ref` in config does NOT re-sync an existing dep.
- Force (`force=True`): every subdirectory of `.goga/usages/` except `cooks` is removed
  (root `*.md` files kept), then all declared deps are re-synced.

## Exit codes

- `0` — success (including "nothing to sync").
- `1` — at least one dep failed (best-effort: other deps still attempted).

## Constraints for consumers

- Call `sync` only from a directory containing `.goga/config.yml`.
- `--force` is the only mechanism to refresh an already-synced dep.
- `cooks/` and root `*.md` in `.goga/usages/` are never touched.
