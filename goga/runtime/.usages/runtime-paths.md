# Runtime directory paths — goga/runtime

## Overview

The `goga.runtime` module owns the single shared formula for host-side runtime
directories used by goga commands that launch containers with persistent state:

    ~/.goga/runtime/<purpose>/<normalized_project>/<branch>/<*suffix_parts>

A "runtime directory" is a host-side location where a container-launched tool
keeps its persistent state across runs of the same project on the same git
branch.

This module is a pure leaf utilities module. Its routines return paths; they
never create directories or write files. Directory creation and cleanup belong
to the consumer.

## Target audience

Implementers of host-side container launchers that need a deterministic,
project-scoped, branch-scoped runtime directory for the tool they launch inside
the container, and implementers of host-side observer commands that reveal or
package the state a launcher left behind — possibly of another branch.

## Public API

    from goga.runtime import resolve_runtime_dir
    from goga.runtime.paths import normalize_project_path, resolve_git_branch

- `resolve_runtime_dir(purpose: str, *suffix_parts: str, branch: str | None = None) -> Path`
  — compose the runtime dir for a given purpose, current project, an explicit
  or git-derived branch, and zero or more trailing suffix segments.
- `normalize_project_path(project_path: Path) -> str` — atomic helper (used
  internally; rarely called directly).
- `resolve_git_branch() -> str` — atomic helper (used internally; rarely called
  directly).

## Typical usage

### Consumer facade pattern

A consumer cell exposes its own thin facade over `resolve_runtime_dir` with its
fixed `purpose` and optional suffix:

    from pathlib import Path
    from goga.runtime import resolve_runtime_dir


    def resolve_<consumer>_runtime_dir(*suffix_parts: str) -> Path:
        return resolve_runtime_dir("<purpose>", *suffix_parts)

The facade does not create the directory. Callers create it (idempotent
`Path.mkdir(parents=True, exist_ok=True)`) before passing the path to docker
`-v`, and wipe it via the consumer's own cleanup routine when an explicit
`--clean` flag is set.

### Addressing another branch's state

An observer command (path query, archiver) passes the explicit branch segment
it received from its user — no git is consulted, deleted branches stay
addressable:

    from goga.runtime import resolve_runtime_dir

    target_dir = resolve_runtime_dir("builds", branch="feature/x")
    # → ~/.goga/runtime/builds/<normalized_project>/feature-x

Omit `branch` (or pass None) for the launcher behavior — the current git
branch with the "default" fallback. The explicit value is slugified by the
same rule as the git-derived one (forward slashes become hyphens), so both
forms address the same directory for the same branch — one formula, no
second path scheme.

### Resulting path shape

For a project at `/Users/wb/IdeaProjects/goga` on branch `feature/x`:

    resolve_runtime_dir("<purpose>")
    → ~/.goga/runtime/<purpose>/Users-wb-IdeaProjects-goga/feature-x

    resolve_runtime_dir("<purpose>", "suffix")
    → ~/.goga/runtime/<purpose>/Users-wb-IdeaProjects-goga/feature-x/suffix

    resolve_runtime_dir("<purpose>", branch="release/1.2")
    → ~/.goga/runtime/<purpose>/Users-wb-IdeaProjects-goga/release-1.2

The project segment is the absolute path with leading slashes stripped and
remaining slashes replaced by hyphens. The branch segment is the current git
branch name with forward slashes replaced by hyphens (e.g. `feature/x` →
`feature-x`), or `"default"` when git is unavailable, the current directory is
not a git repository, or HEAD is detached. An explicit `branch` value replaces
the git lookup and is slugified identically.

## Preconditions

- The consumer must call `resolve_runtime_dir` (or its facade) from the working
  directory that should be treated as the project root.
- The consumer must create the returned directory before bind-mounting it into
  a container.
- The consumer must NOT rely on this module to clean up the directory — cleanup
  is a separate consumer-side concern.
- An explicit `branch` is trusted as-is — no git validation happens here;
  consumers that need existence guarantees check the returned path themselves.

## Side effects

None. All routines in this module are pure with respect to the filesystem.
Passing an explicit `branch` additionally skips the git subprocess call of the
derived form.

## Failure modes

- `resolve_git_branch` never raises. Fallback is the literal `"default"`.
- `resolve_runtime_dir` does not validate `purpose` — the consumer owns the
  namespace — and does not validate `branch` beyond slugification; a wrong
  branch name yields a wrong (possibly non-existent) path, not an error.
