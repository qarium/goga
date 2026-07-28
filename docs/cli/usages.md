# goga usages

`goga usages` manages cell-level usages — the `.usages/*.md` files authored inside a dependency's cells — declared as git dependencies in `.goga/config.yml`. It replaces the legacy ad-hoc `goga sync` command with a config-driven workflow. Two subcommands share one config:

- `goga usages sync` materializes and refreshes usage files from each dep's remote into your project's `.goga/usages/` tree.
- `goga usages status` checks the already-synchronized files against each dep's current remote git state and reports drift — without modifying anything.

Declare your dependencies once in `.goga/config.yml`, then `sync` to materialize them and `status` to detect when they fall behind.

## Synopsis

```bash
goga usages sync [--force]
goga usages status [--info] [--group GROUP] [--dep DEP]
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

## status

`goga usages status` checks already-synchronized cell-level usages against the current state of each dep's remote git repository and reports drift per dep. Where `sync` writes files, `status` only inspects them — it never modifies `.goga/usages/`.

### Synopsis

```bash
goga usages status [--info] [--group GROUP] [--dep DEP]
```

### What It Does

`goga usages status` reads the same top-level `usages:` section of `.goga/config.yml` as `sync` and, for each declared `<group>/<dep>` dependency (after applying the `--group`/`--dep` filters):

1. **Detect `new`** — if `.goga/usages/<group>/<dep>/` does not exist, the dep is reported `new` (declared but never synchronized). No clone happens.
2. **Rebuild the expected tree** — otherwise the remote is cloned at `git`/`ref` into a temp directory and the dep's `.usages/` content is re-deployed from its `root` into a *second* temp directory, mirroring `sync`'s deploy logic but writing only to temp space.
3. **Compare by content hashes** — the local tree under `.goga/usages/<group>/<dep>/` and the rebuilt expected tree are each hashed (regular files by chunked content; symlinks by their readlink string, never followed). Equal hashes → `up to date`; any difference → `out of date`.
4. **Best-effort on failure** — a clone/checkout/deploy failure for one dep is reported `error`; the remaining deps are still checked.

Because there is no stored manifest, `out of date` reports only that the local tree differs from the remote-rebuilt tree — it cannot tell "upstream moved ahead" from "you edited it locally".

### Statuses

Output is a `group/ → dep/` ASCII tree. Every node carries a bracketed marker; directories render with a trailing `/`.

Each **dep** resolves to exactly one state, shown as a marker on the dep node:

| State | Marker | Meaning |
|---|---|---|
| `new` | `[+]` | Target `.goga/usages/<group>/<dep>/` is absent — declared but never synced. |
| `up to date` | `[ ]` | The local tree matches the rebuilt remote tree. |
| `out of date` | `[*]` | The local tree differs from the rebuilt remote tree. |
| `error` | `[!]` | The check failed (clone/checkout/deploy). The line appends a credential-free message. |

With `--info`, each dep is expanded into its **per-node file/folder tree**. Every node (file or directory) carries its own verdict:

| Verdict | Marker | Meaning |
|---|---|---|
| unchanged | `[ ]` | Present in both trees with identical content. |
| modified | `[*]` | Present in both trees but the content differs. |
| added | `[+]` | Present only in the remote-rebuilt tree (a remote-only folder rolls up to `added`, not `out of date`). |
| removed | `[-]` | Present only in the local (synced) tree. |

A directory's verdict is the aggregation of the files beneath it: all unchanged → `[ ]`; all added → `[+]`; all removed → `[-]`; any mix → `[*]`. `new` and `error` deps carry no entries.

Color is applied **only** to the changed markers (`[*]`, `[+]`, `[-]`, `[!]`) — never to `[ ]` or the tree skeleton — and auto-disables outside a TTY (piped output, CI logs), so the same command stays readable in scripts.

### Options

| Option | Default | Description |
|---|---|---|
| `--info`, `-i` | off | Expand each dep into its per-node file/folder tree with per-node status markers. |
| `--group`, `-g` | all | Limit the check to deps under one group. |
| `--dep`, `-d` | all | Limit the check to deps with one name (across all groups). |

A non-matching `--group` or `--dep` yields an empty result, never an error.

### Exit Codes

| Code | Meaning |
|---|---|
| `0` | Every checked dep is `up to date`, or the `usages:` section is absent/empty, or the filters matched nothing. |
| `1` | At least one checked dep is `new`, `out of date`, or `error`. |

A failure to load `.goga/config.yml` (missing file, malformed YAML, schema violation) propagates as a `click.ClickException` with a clean message and exit code `1`, identical to `sync`.

### Read-only

`status` only ever reads `.goga/usages/`. It re-deploys the remote tree into ephemeral temp directories — never into `.goga/usages/`, `cooks/`, or any root `*.md` file. The two temp directories are cleaned up in nested `finally` blocks on both the success and failure paths, so a failed check leaves nothing behind.

### Network cost

Every dep that is not `new` is checked by cloning its remote at the declared `git`/`ref` — there is no caching and no reuse of `sync`'s clones. Use `--group`/`--dep` to check narrowly when you only care about one dependency.

### Examples

Check every declared dep:

```bash
goga usages status
```

```
internal/
└── [+] my-shared-cells/
libs/
├── [ ] click/
└── [*] structlog/
```

Expand into per-node detail:

```bash
goga usages status --info
```

```
internal/
└── [+] my-shared-cells/
libs/
├── [ ] click/
│   └── [ ] cell_1/
│       └── [ ] cell_2/
├── [*] structlog/
│   ├── [*] cell_1/
│   │   └── [*] cell_2/
│   └── [+] new-folder/
│       └── [+] guide.md
```

Check a single dep across all groups:

```bash
goga usages status --dep click
```

## Exit Codes (`sync`)

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
