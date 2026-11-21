# Archiving runtime artifacts — goga runtime archive

## Overview

The `goga runtime archive` subcommand packages exactly one target per
invocation — the build artifacts (`-b/--build`) or one named pipeline's
artifacts (`-p/--pipeline NAME`) — into a single self-contained `.tar.gz`
archive and prints exactly one stdout line: the absolute path of the created
archive. The archive holds one wrapper root directory
`goga-runtime-<target>-<branch>/` containing the target's full recursive
contents with the same relative structure, so a bare extraction cannot
scatter files and the archive opens with standard tools on a machine
without goga.

Run it from the project working directory. The `-b/--branch` group option
(placed before the subcommand) addresses another branch's state exactly as
it does for the path queries — the archive filename and wrapper root use
the same effective branch segment.

## Target audience

Developers preparing a bug report, a backup before `--clean`, or a transfer
of run state between machines — anyone who needs run state as one portable
file without hand-rolled archiving.

## Typical usage

### Archive the build artifacts

    $ goga runtime archive -b
    /home/user/project/goga-runtime-build-feature-x.tar.gz

### Archive one pipeline's artifacts

    $ goga runtime archive -p pybuggy:api-feature
    /home/user/project/goga-runtime-pybuggy-api-feature-feature-x.tar.gz

The `<target>` part of the name is `build` or the sanitized pipeline name
(`:` → `-`, as at run time); the `<branch>` part is the effective branch
segment (the slugified `-b/--branch` value, else the git-derived branch,
else `default`).

Note the deliberate dual meaning of `-b`: before the subcommand token it is
the group's `--branch`, after it the archive flag `--build` —
`goga runtime -b main archive -b` selects the build artifacts of branch
`main`.

### Write to an explicit destination

    $ goga runtime archive -b -o /tmp/report.tar.gz

An explicit destination may overwrite an existing file at that path; an
existing directory under `-o` is an error, and a missing parent directory
is an error (no implicit creation).

## Preconditions

- Exactly one target selection per invocation: neither or both is a usage
  error.
- The target directory must exist: a missing target is an error naming the
  missing path, and no archive file is created. An existing but empty
  target directory is packaged successfully.
- Host-side only: inside the goga image the subcommand fails with a clean
  host-side-only error.

## Side effects

One new artifact: the archive file itself (deletable without consequence).
The source state is never modified, moved, or deleted — archiving is safe
to repeat, subject to the default-name collision rule.

## Failure modes

- Default-name collision: an existing file under the deterministic default
  name is refused — the error points to `-o/--output`; nothing is
  overwritten.
- Unwritable destination: a clean error, and no partial archive file is
  kept; a mid-packaging failure removes the partial archive.
- A `-p` value starting with `-` is a clean error — it would be parsed as
  a flag.
- A `-p` value that is empty or the literal `.`/`..` is a clean error — it
  would package the branch- or project-level directory, not one target.
- A `-p` value containing `/` is a clean error — the sanitized name forms
  the archive stem and the single wrapper root, which must each be one
  directory name.
- The literal `.`/`..` as the group's `-b/--branch` is a clean error — the
  segment would escape the project/branch scope and package a wider tree.

## Notes

- Archives are not byte-reproducible (file metadata is stored as
  encountered); the deterministic contract covers the name and the layout.
- A snapshot taken while a run is actively writing its state may be
  inconsistent — archive between runs.
