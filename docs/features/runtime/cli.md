# goga runtime

Query and archive the host-side runtime state of the current project.

`goga runtime` is a Click group with the subcommands `build`, `pipeline`, and `archive`, over the runtime state tree (`~/.goga/runtime/…`). Everything runs host-side; the path queries are read-only, and `archive` writes exactly one new artifact (the archive file) while never touching the state it packages. Errors surface as clean one-line messages on stderr (exit 1, no traceback); argv-form errors are Click usage errors (exit 2). Stdout carries exactly one result line on success — and nothing else, ever.

## Synopsis

```bash
goga runtime [-b BRANCH] build|pipeline NAME|archive (-b | -p NAME) [-o PATH]
```

## Branch addressing

The effective branch segment — the `<branch>` part of every path and archive name — is resolved once per invocation:

- With the group option `-b`/`--branch`, the given value: every forward slash replaced by a hyphen (`release/1.2` → `release-1.2`), used directly — git is not consulted, no validation happens, so the state of a deleted branch stays addressable and a typo simply addresses a directory that does not exist.
- Without it, the current git branch (slashes → hyphens), falling back to `default` when git is missing, the directory is not a repository, or HEAD is detached.
- An empty value (`-b ""`) counts as not given.

The option belongs to the group and binds only *before* the subcommand token. The short alias `-b` carries two meanings at two parse positions — before the token it is the group's `--branch`; after the `archive` token it is the archive subcommand's `--build` flag. The two never collide: `goga runtime -b main archive -b` selects the build artifacts of branch `main`.

## `goga runtime build`

Prints the build artifacts directory — the directory the build run bind-mounts its persistent state over:

```bash
dir=$(goga runtime build)
# /home/user/.goga/runtime/builds/<normalized-project>/<branch>
```

The path prints even when nothing has ever run — the location is deterministic and nothing is created on disk. Exactly one stdout line.

## `goga runtime pipeline`

Prints the named pipeline's artifacts directory — the directory the pipeline run mounts at `/home/goga/pipeline`:

```bash
tree "$(goga runtime pipeline pybuggy:api)"
# /home/user/.goga/runtime/pipelines/<normalized-project>/<branch>/pybuggy-api
```

NAME is the pipeline name as used at run time; a `:` in it becomes `-` in the path segment, exactly as the run composes it — the printed path is the directory the run actually uses. A name starting with `-` is passed after `--` (`goga runtime pipeline -- -weird`); an empty or dash-leading name is a clean error, not a path. Exactly one stdout line.

## `goga runtime archive`

Packages exactly one target per invocation into a single `.tar.gz` and prints the created archive's absolute path — one line, for scripting:

```bash
goga runtime archive -b                  # the build artifacts
goga runtime archive -p pybuggy:api      # one pipeline's artifacts
goga runtime -b release/1.2 archive -b   # another branch's build artifacts
```

| Option | Kind | Meaning |
|---|---|---|
| `-b`, `--build` | flag | Select the build artifacts directory as the target |
| `-p`, `--pipeline` | value | Select the named pipeline's artifacts directory as the target (sanitized as at run time) |
| `-o`, `--output` | value | Write the archive to this path instead of the default name in the current directory |

Exactly one target selection per invocation — neither or both is a clean error. The archive holds the target's full recursive contents under the single wrapper root `goga-runtime-<target>-<branch>/` (the same string as the default filename), preserving the relative structure — a bare extraction cannot scatter files, special files are preserved as encountered, and the archive opens with standard tools on a machine without goga. The source state is never modified.

### Destination semantics

- **Default name** — `<cwd>/goga-runtime-<target>-<branch>.tar.gz`; an existing file or symlink under that name is a clean collision error pointing to `-o/--output` (nothing is ever overwritten under the default name).
- **Explicit `-o`** — resolved against the current working directory; an existing *file* there is legitimate (the flag itself is the overwrite decision), an existing *directory* is an error, and a missing parent directory is an error — no implicit creation.

A missing target directory is a clean error naming the missing path, and no archive file is created; an existing but empty target directory is packaged successfully. A packaging-time `OSError` (an unwritable destination, for instance) surfaces as a clean error, and no partial archive file is kept — a mid-packaging failure removes the partial.

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success — the path or the created archive's path printed (exactly one line) |
| `1` | A clean domain error: inside the goga image (host-side only), an empty or dash-leading pipeline name, neither/both archive targets, a missing target directory, a default-name collision, an `-o` pointing at a directory or under a missing parent, or a packaging `OSError` |
| `2` | A usage error (a missing NAME, an unknown option, a bare `goga runtime` — which prints help) |

## Notes

- Run from the project working directory — the `<normalized-project>` segment of every path derives from it.
- Archives are not byte-reproducible (file metadata is stored as encountered); the deterministic contract covers the name and the layout.
- A snapshot taken while a run is actively writing its state may be inconsistent — archive between runs.
- The [Build](../build/cli.md#runtime-state-isolation) and [Pipelines](../pipelines/cli.md#persistent-pipeline-state) pages document the two ends of the same tree: where the runs write it, and how this command reads it.
