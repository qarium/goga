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
the container.

## Public API

    from goga.runtime import resolve_runtime_dir
    from goga.runtime.paths import normalize_project_path, resolve_git_branch

- `resolve_runtime_dir(purpose: str, *suffix_parts: str) -> Path` — compose the
  runtime dir for a given purpose, current project, current git branch, and zero
  or more trailing suffix segments.
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

### Resulting path shape

For a project at `/Users/wb/IdeaProjects/goga` on branch `feature/x`:

    resolve_runtime_dir("<purpose>")
    → ~/.goga/runtime/<purpose>/Users-wb-IdeaProjects-goga/feature-x

    resolve_runtime_dir("<purpose>", "suffix")
    → ~/.goga/runtime/<purpose>/Users-wb-IdeaProjects-goga/feature-x/suffix

The project segment is the absolute path with leading slashes stripped and
remaining slashes replaced by hyphens. The branch segment is the current git
branch name with forward slashes replaced by hyphens (e.g. `feature/x` →
`feature-x`), or `"default"` when git is unavailable, the current directory is
not a git repository, or HEAD is detached.

## Preconditions

- The consumer must call `resolve_runtime_dir` (or its facade) from the working
  directory that should be treated as the project root.
- The consumer must create the returned directory before bind-mounting it into a
  container.
- The consumer must NOT rely on this module to clean up the directory — cleanup
  is a separate consumer-side concern.

## Side effects

None. All routines in this module are pure with respect to the filesystem.

## Failure modes

- `resolve_git_branch` never raises. Fallback is the literal `"default"`.
- `resolve_runtime_dir` does not validate `purpose` — the consumer owns the
  namespace.
