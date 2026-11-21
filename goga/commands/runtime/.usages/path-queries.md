# Runtime path queries — goga runtime build / pipeline

## Overview

The `goga runtime build` and `goga runtime pipeline <name>` subcommands print
the exact host location of the runtime state a `goga build` or `goga pipeline`
run uses for the current project. Each prints exactly one line on stdout —
the absolute directory path — and nothing else: no banners, no progress
output. Errors go to stderr with a non-zero exit.

Run them from the project working directory; the location identity derives
from the current directory and the current git branch.

## Target audience

Developers and scripts that need the artifacts location of the current
project — for inspection, reporting, or wiring into other tools
(`dir=$(goga runtime build)`), on the host where the runs happened.

## Typical usage

### Locate build artifacts

    $ goga runtime build
    /home/user/.goga/runtime/builds/Users-wb-IdeaProjects-goga/feature-x

The path prints even when nothing has ever run — the location is
deterministic and nothing is created on disk.

### Locate pipeline artifacts

    $ goga runtime pipeline pybuggy:api-feature
    /home/user/.goga/runtime/pipelines/.../pybuggy-api-feature

The name is sanitized exactly as the run sanitizes it (`:` → `-`), so the
printed path is the directory the run actually uses.

### Address another branch's state

    $ goga runtime -b release/1.2 build

The `-b/--branch` group option (placed before the subcommand) replaces the
git-derived branch segment with the slugified given value (`/` → `-`). No
git validation happens — deleted branches stay addressable; a typo produces
a path whose directory simply does not exist. Without the option the branch
is git-derived, falling back to `default` outside a repository or on a
detached HEAD. An empty value means "not given".

### Scripting contract

    dir=$(goga runtime build)
    tree "$(goga runtime pipeline my-pipeline)"

Stdout carries the single result line only; anything else a command prints
goes to stderr, so command substitution stays clean.

## Preconditions

- Run from the project working directory (the project segment of the path
  derives from it).
- Host-side only: inside the goga image every runtime subcommand fails with
  a clean host-side-only error.

## Side effects

None. Path queries create, modify, and delete nothing; repeat invocations
return the same value.

## Failure modes

- A missing NAME for `pipeline` is a usage error (non-zero exit).
- A NAME starting with `-` is a clean error — it would be parsed as a flag.
