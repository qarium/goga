# Runtime — API

The facade of the domain package **`goga.commands.runtime`** — the host-side observer surface over the runtime state tree. The path composition itself lives in the leaf cell `goga.runtime` (`resolve_runtime_dir` there is the one shared formula every printed path and archive target goes through); this facade carries the branch/target resolution, the destination semantics, the packaging, and the Click group.

The signatures below are the CODEMANIFEST contract of the cell.

## Branch and target resolution

```python
resolve_effective_branch(branch: str | None = None) -> str
resolve_build_target_dir(branch_segment: str) -> Path
sanitize_pipeline_name(name: str) -> str
resolve_pipeline_target_dir(pipeline_name: str, branch_segment: str) -> Path
```

The effective branch segment (`None`/`""` mean not given — the slugified current git branch with its `default` fallback; a non-empty value is slugified — slashes to hyphens — and used directly, git-free). The two target resolvers compose `~/.goga/runtime/builds|pipelines/<normalized-project>/<branch>/…` through the shared formula; `sanitize_pipeline_name` is the literal `:` → `-` transformation the pipeline run composes for its state segment. All four are pure — nothing on disk is created.

## Archive destination and packaging

```python
resolve_archive_destination(archive_stem: str, output: str | None = None) -> Path
package_runtime_archive(target_dir: Path, wrapper_root: str, destination: Path) -> Path
```

The resolver validates only — the deterministic default name (an existing file or symlink there is a `click.ClickException` collision pointing to `-o/--output`), or the explicit path with strict semantics (an existing file expresses overwrite intent; a directory or a missing parent is an error). The packager writes the full recursive contents of `target_dir` under the single `wrapper_root` directory into `destination` (`tarfile` `w:gz`, no dereference) and returns the path; on any packaging failure it removes the partial archive it created and re-raises (`OSError` — the command layer wraps it into a clean error).

## The command group

```python
runtime(branch: str | None = None)
```

The Click group registered on the root `goga` app — the `build`, `pipeline`, and `archive` subcommands (see [CLI](cli.md)). The group is re-exported by the `goga.commands` facade.

## Example

```python
from goga.commands.runtime import package_runtime_archive, resolve_build_target_dir, resolve_effective_branch

segment = resolve_effective_branch()  # e.g. "feature-x" (git-derived) or an explicit value
target = resolve_build_target_dir(segment)  # ~/.goga/runtime/builds/<project>/<segment>

archive = package_runtime_archive(
    target,
    wrapper_root="goga-runtime-build-" + segment,
    destination=Path.cwd() / f"goga-runtime-build-{segment}.tar.gz",
)
```
