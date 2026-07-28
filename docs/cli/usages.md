# goga usages

`goga usages` synchronizes cell-level usages — the `.usages/*.md` files authored inside a dependency's cells — from declared git dependencies into your project's `.goga/usages/` tree. It replaces the legacy ad-hoc `goga sync` command with a config-driven workflow: declare your dependencies once in `.goga/config.yml`, then run one command to materialize and refresh their usage files.

## Synopsis

```bash
goga usages sync [--force]
```

## What It Does

`goga usages sync` reads the top-level `usages:` section of `.goga/config.yml` and, for each declared `<group>/<dep>` git dependency:

1. **Resolve** the dependency's git URL and optional ref (branch, tag, or commit) from `ProjectConfig.usages`.
2. **Skip** the dep when its target directory already exists and `--force` was not passed (incremental mode).
3. **Clone** the source repository into a fresh temp directory via stock `git` (no token injection).
4. **Deploy** every `.usages/` folder found under the dep's optional `root` into `.goga/usages/<group>/<dep>/`, dropping the `.usages` segment from destination paths.
5. **Clean up** the temp directory in a `finally` block (on success) or before re-raising (on failure, so a failed clone never leaks a temp directory).

When `--force` is passed, `.goga/usages/` is cleaned first: every subdirectory except `cooks` is removed, root files are preserved, then every declared dep is re-synced from scratch.

### Nothing to sync

When `.goga/config.yml` has no `usages:` section, `config.usages` is `None` and `goga usages sync` exits `0` immediately without touching git or the filesystem.

### Root directive

Each dependency may declare an optional `root` — a subpath inside the cloned repository from which `.usages` folders are discovered and against which destination paths are computed. Absent `root` (or an empty-string `root: ""`) → deploy walks from the clone root.

For every `.usages` folder found under `root`, its contents are copied to the path of its **parent relative to `root`**, with the `.usages` segment dropped. Intermediate non-cell directories are preserved verbatim, so placement is deterministic.

With `root: folder` and target `.goga/usages/libs/click/`:

- `folder/cell_1/cell_2/.usages` → `.goga/usages/libs/click/cell_1/cell_2/`
- `folder/subfolder/cell_1/cell_2/.usages` → `.goga/usages/libs/click/subfolder/cell_1/cell_2/`
- `folder/subfolder/cell_1/another_folder/cell_2/.usages` → `.goga/usages/libs/click/subfolder/cell_1/another_folder/cell_2/`

A `.usages` folder sitting directly at `root` (empty relative path) copies into the dep's target root.

`root` is structurally validated at config-load time: it must be relative (no leading `/` or UNC `//host/share`) and must not contain `..` segments. A `root` that does not resolve to an existing directory inside the clone (missing, or a file) fails the dep with an explicit error rather than producing an empty result.

**Breaking change — no more smoothing.** A repository containing a single `.usages` folder is no longer flattened into the dep root automatically. It lands at its `root`-relative path — at the dep root only when it sits directly at `root`. If you relied on the previous single-`.usages` flattening, declare an explicit `root` or move the `.usages` folder to the repo root.

### Symlink handling

`.usages/` files inside a freshly cloned third-party repository are copied verbatim, including symlinks — symlinks are **not** dereferenced. Dereferencing untrusted symlinks would copy the contents of arbitrary local files or directories the links point at into `.goga/usages/`, which is a local-file disclosure and aggregation vector. Copying the link entries themselves never reads their targets.

## Modes

| Mode | When | Behavior |
|---|---|---|
| **Incremental** (default) | `.goga/config.yml` has a `usages:` section | For each declared dep: skip if `.goga/usages/<group>/<dep>/` exists, otherwise clone and deploy. |
| **Force** | `--force` / `-f` passed | Clean `.goga/usages/` (every subdir except `cooks`; root files preserved), then re-sync every declared dep. |
| **Nothing to sync** | `usages:` section absent | No-op — exits `0` without invoking git. |

## Options

| Option | Default | Description |
|---|---|---|
| `--force`, `-f` | off | Clean `.goga/usages/` (except `cooks` and root files) then re-sync all deps. |

## Configuration

Declare dependencies under the top-level `usages:` key in `.goga/config.yml`. The mapping is two levels deep: `<group>` → `<dep>` → `{ git, ref, root }`.

```yaml
usages:
  libs:
    click:
      git: https://github.com/pallets/click.git
      ref: 8.1.7         # optional — branch, tag, or commit; omit for the default branch
      root: docs         # optional — subpath inside the repo to walk .usages from; omit for the clone root
    structlog:
      git: https://github.com/hynek/structlog.git
  internal:
    my-shared-cells:
      git: git@github.com:myorg/shared-cells.git
      ref: main
```

After the next `goga usages sync`, the cloned `.usages/` content lands at:

```
.goga/usages/libs/click/...
.goga/usages/libs/structlog/...
.goga/usages/internal/my-shared-cells/...
```

### Field reference

| Field | Type | Required | Description |
|---|---|---|---|
| `usages` | mapping | No | Top-level section. `None` (absent) is a no-op for `goga usages sync`. A non-mapping value raises `ValueError`. |
| `usages.<group>` | mapping | Yes when `usages` is present | Group bucket. The key becomes a top-level subdirectory of `.goga/usages/`. |
| `usages.<group>.<dep>` | mapping | Yes when `<group>` is present | Dependency entry. The key becomes a subdirectory under the group. |
| `usages.<group>.<dep>.git` | string | Yes | Git URL of the source repository. Must be non-empty. |
| `usages.<group>.<dep>.ref` | string | No | Git ref — branch, tag, or commit. `None` (omitted) clones the default branch. |
| `usages.<group>.<dep>.root` | string | No | Subpath inside the clone to discover `.usages` folders from. Absent (or an empty string) → clone root. Must be relative; no `..` or absolute paths. |

### Path-segment validation

Each `<group>` and `<dep>` key flows verbatim into a filesystem path under `.goga/usages/`. The loader rejects keys that would escape the target root:

- empty string
- `.` or `..`
- any name containing `/` or `\`

These raise `ValueError` at config-load time, before any git operation, so a malformed config can never traverse outside `.goga/usages/`.

## Examples

Incremental sync — skip deps whose target directory already exists:

```bash
goga usages sync
```

Force a full re-sync — clean `.goga/usages/` (preserving `cooks` and root files), then re-clone every declared dep:

```bash
goga usages sync --force
```

Declare a dependency and sync it for the first time:

```yaml
# .goga/config.yml
usages:
  libs:
    click:
      git: https://github.com/pallets/click.git
      ref: 8.1.7
```

```bash
goga usages sync
# → .goga/usages/libs/click/... populated
```

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | All declared deps synced successfully, or `usages:` section absent (nothing to sync) |
| `1` | One or more deps failed to clone or deploy (best-effort: remaining deps still run, per-dep errors are logged) |

A failure to load `.goga/config.yml` (missing file, malformed YAML, schema violation) propagates as a `click.ClickException` with a clean message and exit code `1` — the raw exception is never shown to the CLI user.

## Notes

- The `cooks` subdirectory and every root `*.md` file in `.goga/usages/` are preserved even under `--force`. Hand-authored content lives there and is never touched by sync.
- Sources are git only — there is no local-path mode. Point `git:` at any reachable repository.
- Authentication uses stock git credentials (SSH agent, credential helper, `.gitconfig`). The command does not inject tokens into clone URLs.
- Per-dep errors are best-effort: if one dep fails to clone or deploy, sync logs the error, continues with the remaining deps, and exits `1`. Inspect `.goga/usages/<group>/<dep>/` to see which deps succeeded.
