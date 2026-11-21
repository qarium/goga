# Architecture Plan — `goga runtime` command group

## Topic

Short name: **goga runtime — host-side path queries and single-target archiver**
Plan path: `.goga/history/2026/add-runtime-command/arch.md` (topic `add-runtime-command`).

Behavioral sources (normative, fixed): `prd.md` (R1–R18), `adr.md`, `task.md` in this topic
directory. This plan fixes the code placement only — cells, CODEMANIFEST contracts, and
usage files.

Design decisions settled during prototyping:

1. **Branch override integration** — parameter extension of `resolve_runtime_dir`
   (keyword-only `branch: str | None = None`); one formula owner, full backward
   compatibility, no second path scheme.
2. **In-image detection** — import of the existing `is_in_docker` fact from `goga/docker`;
   the marker rule keeps a single owner, consistent with the other dual-substrate commands.

## Implementation Order

| # | Cell | Action | Reason for the order |
|---|------|--------|----------------------|
| 1 | `goga/runtime` | modify | Leaf with no Imports; every other artifact depends on its extended signature |
| 2 | `goga/commands/runtime` | **create** | Depends on cell 1 (Types + usage) and on `goga/docker` (untouched leaf); no other new cell depends on it except the facade |
| 3 | `goga/commands` | modify | Facade re-exports the new command from cell 2 (Import + embedding); requires cell 2 to exist |
| 4 | `goga` (root) | modify | Registers the command in the `app` command table; requires the facade (cell 3) to re-export it |

Usage files of each cell are created/updated together with that cell's step (the facade's
`cli-commands.md` at step 3).

## Artifacts

---

### 1. Cell `goga/runtime` — CODEMANIFEST (modify)

Diff against the current `goga/runtime/CODEMANIFEST`:

**ADD** — one paragraph in the global `Annotations:`, inserted after the "Consumers call
resolve_runtime_dir with their purpose and optional suffix; they do not import the atomic
helpers directly unless a facade composes them." paragraph:

```yaml
  An optional explicit branch segment lets host-side observers address another
  branch's state without git involvement; without it the branch is git-derived
  exactly as before. Existing consumers pass no branch and observe no change.
```

**REPLACE** — the entire `"resolve_runtime_dir(...)"` body block (signature key and its
`location` + `annotations`) with:

```yaml
"resolve_runtime_dir(purpose: str, ...suffix_parts: str, branch: str | None = None) -> runtime_dir: Path":
  location: paths.py
  annotations: |
    Compose the host-side runtime directory path for a given purpose, the
    current project, an explicit or git-derived branch, and zero or more
    trailing suffix segments.

    `purpose`: runtime namespace segment — e.g. "builds" or "pipelines".
               Becomes the directory immediately under ~/.goga/runtime/.
    `...suffix_parts`: zero or more trailing path segments appended after the
                    branch directory. Empty (the default) yields the
                    branch-level directory itself. A single suffix is used by
                    pipeline (pipeline_name); multiple suffixes are reserved
                    for future consumers with deeper namespace requirements.
    `branch`: optional explicit branch segment. None or the empty string means
              "not given" — the branch is derived from git via
              `resolve_git_branch` (with its "default" fallback). A non-empty
              value is slugified by the same rule as `resolve_git_branch`
              (every forward slash replaced by a hyphen) and used directly —
              git is not consulted and no branch validation is performed (the
              formula stays pure and git-free; state of a deleted branch is a
              legitimate address; typos surface as the consumer's
              missing-target error).
    `runtime_dir`: absolute host path
                   ~/.goga/runtime/<purpose>/<normalized_project>/<branch>/<*suffix_parts>

    Apply the `convention` practice for docstring style and intra-package imports.

    Algorithm:
    1. Take the current working directory as the absolute project path
    2. Normalize the project path via `normalize_project_path`
    3. Resolve the branch segment: a non-empty `branch` is used with every
       forward slash replaced by a hyphen; otherwise derive it via
       `resolve_git_branch` (slugified git branch or the "default" fallback)
    4. Compose the runtime dir under the user's goga runtime area as
       <purpose>/<normalized>/<branch>/<joined suffix_parts>
    5. Return the composed absolute path

    Requirements:
    - Return value is an absolute path
    - Pure with respect to the filesystem — does not create the directory
      (creation is the caller's responsibility)
    - Empty `...suffix_parts` yields the branch-level directory
    - Multiple `...suffix_parts` are joined in order with the OS separator
    - A non-empty `branch` produces exactly the path the git-derived form
      produces for that branch — one formula, no second path scheme
    - Slugification is idempotent — an already-slugified `branch` value
      passes through unchanged

    Constraints:
    - Do not create the directory here — the caller handles creation
    - Do not validate `purpose` against a whitelist — any non-empty string
      is accepted; the caller owns the namespace
    - Do not validate suffix values semantically — they are path segments only
    - Do not consult git or validate the branch when `branch` is non-empty —
      no subprocess call, no repository check, no existence check
```

**KEEP UNCHANGED** — the `normalize_project_path` and `resolve_git_branch` body blocks,
the header `Usages:` directive.

**REPLACE** — the footer `Description:` with:

```yaml
Description: |
  Pure leaf utilities module for runtime-directory path composition. Owns the
  single shared formula
  ~/.goga/runtime/<purpose>/<normalized_project>/<branch>/<*suffix_parts>
  and exposes two atomic helpers plus one composite routine. Consumers call
  resolve_runtime_dir with their purpose, optional suffix, and optional
  explicit branch segment; atomic helpers are consumed inside
  resolve_runtime_dir.
```

**Footer metadata** — `Author: Goga`, `CreatedAt: 07/07/26` unchanged.

---

### 1a. Cell `goga/runtime` — usage file (modify)

**File:** `goga/runtime/.usages/runtime-paths.md` — full updated content:

````md
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
````

---

### 2. Cell `goga/commands/runtime` — CODEMANIFEST (create)

**File:** `goga/commands/runtime/CODEMANIFEST` — full content:

```yaml
Imports:
  - Types:
      - resolve_runtime_dir
      - resolve_git_branch
    Usages:
      - runtime-paths
    From: goga/runtime
  - Types:
      - is_in_docker
    From: goga/docker

Usages:
  convention: .goga/usages/conventions.md
  click: .goga/usages/cooks/click.md
  tarfile: .goga/usages/cooks/tarfile.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  Use the `click` practice to build the runtime command group: the group
  decorator with its branch option placed before the subcommand token, the
  subcommand registration, the mutually exclusive archive flags, the echo
  and error surfaces, and the exit-code propagation.

  Use the `runtime-paths` practice for the location identity behind every
  printed path and archive target: the consumer facade over the shared
  runtime formula, the path shape, and the purity guarantees.

  Use the `tarfile` practice for the packaging step of the archive
  subcommand: the compressed archive open mode, the wrapper-root naming of
  the tree inside the archive, and the partial-archive removal on failure.

  This cell is the host-side observer surface of the runtime state: a thin
  wrapper that resolves inputs, delegates every path computation to the
  runtime formula, and renders exactly one result line per command. Path
  subcommands are read-only queries; the archive subcommand writes exactly
  one new artifact — the archive file — and never touches the state it
  packages. Every subcommand refuses to run inside the goga image with a
  clean host-side-only error. All errors are human-readable messages on
  stderr with non-zero exits; stdout is reserved for the single result
  line. Use relative imports.

---

"runtime(branch: str | None = None)":
  location: runtime.py
  annotations: |
    The goga runtime command group — a click.Group container for the
    runtime subcommands. Exported via __all__ and registered in the root
    application group. The group carries the branch scope every
    subcommand shares.

    `branch`: the -b/--branch group option — an explicit branch segment
              replacing the git-derived one; None and the empty string
              mean no branch given; the option is passed before the
              subcommand and applies to every subcommand of the group.
              No git validation is performed — the value is slugified and
              trusted (state of a deleted branch is a legitimate address;
              a typo surfaces as the archive subcommand's missing-target
              error).

    Use the `click` practice for the group decorator, the group option,
    and the subcommand registration.

    Subcommand surfaces:
    - build — no arguments, no options
    - pipeline — a required NAME positional
    - archive — the mutually exclusive -b/--build flag and -p/--pipeline
      NAME pair, plus the -o/--output destination option

    The short alias -b deliberately carries two meanings — the group's
    --branch and the archive subcommand's --build. Click binds group
    options only before the subcommand token and subcommand options only
    after it, so the parse positions never collide; both meanings are
    documented in the help texts.

    A bare group invocation prints help and exits 0.

    Apply the `convention` CLI command docstring rule for the --help text
    (rendered verbatim by Click; omit Args/Returns/Raises).
  methods:
    "build() -> exit_code: int": |
      Subcommand goga runtime build: print the host location of the build
      artifacts directory of the current project and the effective branch —
      and nothing else.

      `exit_code`: 0 on success, 1 on error

      Algorithm:
      1. Refuse inside the goga image: `is_in_docker` returning True is a
         clean host-side-only error (stderr, non-zero exit)
      2. Resolve the effective branch segment via `resolve_effective_branch`
         with the group branch
      3. Resolve the target directory via `resolve_build_target_dir`
      4. Echo the resolved path to stdout — exactly one line, nothing else

      Requirements:
      - Prints the path and only the path — no decoration, no trailing text
      - The path is printed even when the directory does not yet exist
      - Nothing is created, modified, or deleted on disk

      Constraints:
      - Do not create or verify the directory — this subcommand is a pure
        query
      - Do not print anything besides the path on stdout

    "pipeline(name: str) -> exit_code: int": |
      Subcommand goga runtime pipeline: print the host location of the named
      pipeline's artifacts directory — and nothing else.

      `name`: required NAME positional — the pipeline name as used at run
              time; sanitized exactly as the run composes its state segment
      `exit_code`: 0 on success, 1 on error

      Algorithm:
      1. Refuse inside the goga image: `is_in_docker` returning True is a
         clean host-side-only error (stderr, non-zero exit)
      2. Reject a `name` starting with "-" as a clean error (argv
         parsability)
      3. Resolve the effective branch segment via `resolve_effective_branch`
         with the group branch
      4. Resolve the target directory via `resolve_pipeline_target_dir`
      5. Echo the resolved path to stdout — exactly one line, nothing else

      Requirements:
      - A missing NAME is a usage error with a non-zero exit
      - The name's sanitization matches the run-time state segment, so the
        printed path is the directory the run actually uses
      - The path is printed even when the directory does not yet exist
      - Nothing is created, modified, or deleted on disk

      Constraints:
      - Do not validate that the pipeline exists — the name addresses a
        state directory, not a pipeline file
      - Do not print anything besides the path on stdout

    "archive(build: bool = False, pipeline: str | None = None, output: str | None = None) -> exit_code: int": |
      Subcommand goga runtime archive: package exactly one target per
      invocation — the build artifacts directory or one named pipeline's
      artifacts directory — into a single self-contained compressed archive
      under a wrapper root, and print the created archive's path.

      `build`: the -b/--build flag — select the build artifacts as the
               target
      `pipeline`: the -p/--pipeline value — select the named pipeline's
                  artifacts as the target
      `output`: the -o/--output value — an explicit archive destination
                path; absent means the deterministic default name
      `exit_code`: 0 on success, 1 on error

      Algorithm:
      1. Refuse inside the goga image: `is_in_docker` returning True is a
         clean host-side-only error (stderr, non-zero exit)
      2. Validate the target selection: exactly one of `build`, `pipeline`
         must be given — neither or both is a usage error; a `pipeline`
         value starting with "-" is a clean error (argv parsability)
      3. Resolve the effective branch segment via `resolve_effective_branch`
         with the group branch
      4. Resolve the target: the build selection resolves the directory via
         `resolve_build_target_dir` with the target label "build"; the
         pipeline selection resolves it via `resolve_pipeline_target_dir`
         with the target label taken from `sanitize_pipeline_name`
      5. A target directory that does not exist is a clean error naming the
         missing path — no archive file is created; an existing but empty
         directory is a legitimate target
      6. Compose the archive stem goga-runtime-<target label>-<branch
         segment> — the base of both the default archive filename and the
         wrapper root inside the archive
      7. Resolve the destination via `resolve_archive_destination` with the
         stem and `output`
      8. Package via `package_runtime_archive` with the target directory,
         the wrapper root equal to the stem, and the destination
      9. Echo the created archive's absolute path to stdout — exactly one
         line, nothing else

      Requirements:
      - The archive contains the full recursive contents of the target
        directory under the single wrapper root directory, with the same
        relative structure; special files are preserved as encountered —
        no dereference, no content filters
      - The archive is a self-contained .tar.gz openable with standard
        tools without goga
      - The source state is left unmodified — the only new artifact is the
        archive file itself
      - On success, stdout carries exactly the created archive's absolute
        path and the file exists at that path
      - Every failure leaves no partial archive file behind

      Constraints:
      - Do not package more than one target per invocation — no bulk mode
      - Do not modify, move, or delete anything inside the target directory
      - Do not print anything besides the archive path on stdout
      - Do not extract, restore, or list archive contents — packaging only

"resolve_effective_branch(branch: str | None = None) -> segment: str":
  location: targets.py
  annotations: |
    Resolve the effective branch segment — the branch part of the location
    identity every runtime subcommand addresses.

    `branch`: the raw group option value; None and the empty string mean
              no branch given
    `segment`: the effective branch segment — a single filesystem-safe
               path component

    Algorithm:
    1. A non-empty `branch` returns with every forward slash replaced by a
       hyphen — no git consultation, no validation
    2. Otherwise delegate to `resolve_git_branch` — the slugified current
       git branch with the "default" fallback

    Requirements:
    - Deterministic — the same input produces the same segment on every
      call
    - Idempotent to an already-slugified input — the segment passes
      through unchanged
    - Pure with respect to the filesystem — only the derived form reads
      git

    Constraints:
    - Do not validate the branch against the repository — a deleted
      branch's state is a legitimate address
    - Do not replace characters other than forward slashes

"resolve_build_target_dir(branch_segment: str) -> target_dir: Path":
  location: targets.py
  annotations: |
    Resolve the build artifacts directory of the current project for the
    given effective branch segment.

    `branch_segment`: the effective branch segment produced by
                      `resolve_effective_branch`
    `target_dir`: absolute host path of the build artifacts directory

    Use the `runtime-paths` practice for the consumer facade pattern over
    the shared formula.

    Algorithm:
    1. Delegate to `resolve_runtime_dir` with the purpose "builds", no
       suffix parts, and `branch_segment` as the branch — no further
       namespace exists under the branch directory
    2. Return the resulting path

    Requirements:
    - Pure with respect to the filesystem — the directory is not created

    Constraints:
    - Do not add a suffix — build has no namespace below the branch
      directory

"sanitize_pipeline_name(name: str) -> sanitized: str":
  location: targets.py
  annotations: |
    Sanitize a pipeline name into its host path segment and target label:
    every colon is replaced by a hyphen.

    `name`: the pipeline name as used at run time
    `sanitized`: the colon-free segment — the same transformation the run
                 composes for its state directory

    Requirements:
    - Literal one-to-one replacement — no collapsing, no trimming
    - Deterministic and pure

    Constraints:
    - Do not sanitize for any use other than the host path segment and the
      archive target label — other consumers keep the original name

"resolve_pipeline_target_dir(pipeline_name: str, branch_segment: str) -> target_dir: Path":
  location: targets.py
  annotations: |
    Resolve the artifacts directory of the named pipeline of the current
    project for the given effective branch segment.

    `pipeline_name`: the pipeline name as used at run time
    `branch_segment`: the effective branch segment produced by
                      `resolve_effective_branch`
    `target_dir`: absolute host path of the pipeline's artifacts directory

    Use the `runtime-paths` practice for the consumer facade pattern over
    the shared formula.

    Algorithm:
    1. Sanitize the name via `sanitize_pipeline_name`
    2. Delegate to `resolve_runtime_dir` with the purpose "pipelines", the
       sanitized name as the single suffix part, and `branch_segment` as
       the branch
    3. Return the resulting path

    Requirements:
    - The sanitized suffix matches the run-time state segment — the
      resolved path is the directory the run actually uses
    - Pure with respect to the filesystem — the directory is not created

    Constraints:
    - Do not validate that the pipeline exists — the name addresses a
      state directory, not a pipeline file

"resolve_archive_destination(archive_stem: str, output: str | None = None) -> destination: Path":
  location: archive.py
  annotations: |
    Resolve the archive destination path under strict destination
    semantics: the deterministic default name, or an explicit override
    that expresses overwrite intent.

    `archive_stem`: the archive stem — the base of the default filename
    `output`: the -o/--output value; None means the default
    `destination`: absolute path the archive is written to

    Algorithm:
    1. Without `output`: compose <current working directory>/<archive_stem>
       .tar.gz; an existing file at that path is a clean collision error
       naming the path and pointing to -o/--output; otherwise return it
    2. With `output`: an existing directory at the path is a clean error;
       a missing parent directory is a clean error — no implicit
       creation; an existing file is legitimate — an explicit destination
       expresses the intent to overwrite
    3. Return the absolute destination path

    Requirements:
    - Nothing is written or created by this routine — it resolves and
      validates only; the unwritable-destination failure surfaces at the
      packaging step, which leaves no partial file

    Constraints:
    - Do not create missing parent directories — predictability over
      convenience
    - Do not overwrite or refuse an existing file under an explicit
      destination — the flag itself is the overwrite decision

"package_runtime_archive(target_dir: Path, wrapper_root: str, destination: Path) -> archive_path: Path":
  location: archive.py
  annotations: |
    Package the full recursive contents of the target directory into a
    single compressed archive under the wrapper root, writing nothing else
    and leaving the source untouched.

    `target_dir`: the target directory — guaranteed by the caller to exist
    `wrapper_root`: the single root directory name holding the whole tree
                    inside the archive
    `destination`: the resolved destination path — validated by the caller
    `archive_path`: the absolute path of the created archive

    Use the `tarfile` practice for the compressed open mode, the
    wrapper-root naming of the added tree, and the failure cleanup.

    Algorithm:
    1. Open the destination for compressed writing — an unwritable
       destination fails here before any data is written
    2. Add the target directory recursively under the wrapper root: the
       full contents as encountered, special files preserved, no
       dereference, no filters
    3. Close the archive and return its absolute path
    4. On any failure during packaging: close, remove the partial archive
       file, and surface the error — nothing partial is kept

    Requirements:
    - The archive layout is one wrapper root directory containing the
      target's full tree with the same relative structure — a bare
      extraction cannot scatter files
    - The source directory is read only — nothing inside it is modified,
      moved, or deleted
    - The returned path is where the file exists on success

    Constraints:
    - Do not filter, exclude, or transform any content — the full
      recursive contents are taken literally
    - Do not keep a partial archive file on any failure path

---

Author: Goga
CreatedAt: 21/11/26
Description: |
  The goga runtime command group — host-side read-only queries of runtime
  artifact locations and a single-target archiver over the shared runtime
  formula.
```

---

### 2a. Cell `goga/commands/runtime` — usage files (create)

**File:** `goga/commands/runtime/.usages/path-queries.md` — full content:

````md
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
````

**File:** `goga/commands/runtime/.usages/archive.md` — full content:

````md
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

## Notes

- Archives are not byte-reproducible (file metadata is stored as
  encountered); the deterministic contract covers the name and the layout.
- A snapshot taken while a run is actively writing its state may be
  inconsistent — archive between runs.
````

---

### 3. Cell `goga/commands` — CODEMANIFEST (modify)

Diff against the current `goga/commands/CODEMANIFEST`:

**ADD** — Imports entry (after the last existing entry, the `hooks` import):

```yaml
  - Types:
      - runtime
    Usages:
      - path-queries
      - archive
    From: goga/commands/runtime
```

**ADD** — two paragraphs at the end of the global `Annotations: |` block:

```yaml
  Use the `path-queries` practice for consumer scenarios of the runtime
  path queries: the one-line stdout contract of the build and pipeline
  subcommands, the branch option semantics, and the scripting patterns.

  Use the `archive` practice for consumer scenarios of the runtime archive
  subcommand: the single-target selection, the deterministic archive naming
  with its wrapper root, the destination semantics, and the failure modes.
```

**ADD** — embedding line at the end of the body re-export list:

```yaml
->runtime: {}
```

**KEEP UNCHANGED** — the `Usages:` directive, all other Imports/embeddings,
the footer.

---

### 3a. Cell `goga/commands` — usage file (modify)

**File:** `goga/commands/.usages/cli-commands.md` — full updated content:

````md
# CLI Commands — goga/commands facade

The `goga.commands` package is a facade that re-exports 19 CLI commands. Each command is a `click.Command` registered in a click group. Each subcell is an independent Python package (`goga/commands/<name>/`) with implementation in `<name>.py` and re-export through `__init__.py`.

## Import

All commands are available from the facade in a single line:

```python
from goga.commands import (
    lint,
    build,
    connect,
    schema,
    codegraph,
    drift,
    contract,
    config,
    usages,
    tool,
    init,
    pipeline,
    upgrade,
    install,
    uninstall,
    history,
    hooks,
    topics,
    runtime,
)
```

Each command is available from its subcell (via `__init__.py` re-export):

```python
from goga.commands.lint import lint
from goga.commands.build import build
from goga.commands.connect import connect
from goga.commands.schema import schema
from goga.commands.codegraph import codegraph
from goga.commands.drift import drift
from goga.commands.contract import contract
from goga.commands.config import config
from goga.commands.usages import usages
from goga.commands.tool import tool
from goga.commands.init import init
from goga.commands.pipeline import pipeline
from goga.commands.upgrade import upgrade
from goga.commands.install import install
from goga.commands.install import uninstall
from goga.commands.history import history
from goga.commands.hooks import hooks
from goga.commands.topics import topics
from goga.commands.runtime import runtime
```

## Registration in click group

```python
import click

from goga.commands import (
    lint,
    build,
    connect,
    schema,
    codegraph,
    drift,
    contract,
    config,
    usages,
    tool,
    init,
    pipeline,
    upgrade,
    install,
    uninstall,
    history,
    hooks,
    topics,
    runtime,
)


@click.group()
def app() -> None:
    """Goga — CODEMANIFEST validation tool."""


app.add_command(lint)
app.add_command(build)
app.add_command(connect)
app.add_command(schema)
app.add_command(codegraph)
app.add_command(drift)
app.add_command(contract)
app.add_command(config)
app.add_command(usages)
app.add_command(tool)
app.add_command(init)
app.add_command(pipeline)
app.add_command(upgrade)
app.add_command(install)
app.add_command(uninstall)
app.add_command(history)
app.add_command(hooks)
app.add_command(topics)
app.add_command(runtime)
```

## Testing with CliRunner

```python
from click.testing import CliRunner
from goga.commands.lint import lint


def test_example():
    runner = CliRunner()
    result = runner.invoke(lint, ["."])
    assert result.exit_code in (0, 1)
```

## Command list

| Command     | Subcell                   | Purpose                              |
|-------------|---------------------------|--------------------------------------|
| `lint`      | `goga/commands/lint/`     | CODEMANIFEST file validation         |
| `build`     | `goga/commands/build/`    | Build via ralphex                    |
| `connect`   | `goga/commands/connect/`  | Connect goga skills                  |
| `schema`    | `goga/commands/schema/`   | Project JSON schema                  |
| `codegraph` | `goga/commands/codegraph/` | Prospective cell graph from existing code |
| `drift`     | `goga/commands/drift/`    | Contract drift between schema and codegraph |
| `contract`  | `goga/commands/contract/` | Compare contract with implementation |
| `config`    | `goga/commands/config/`   | Output configuration values          |
| `usages`    | `goga/commands/usages/`   | Synchronize cell-level usages        |
| `tool`      | `goga/commands/tool/`     | Run tool commands                    |
| `init`      | `goga/commands/init/`     | Initialize goga project              |
| `pipeline`  | `goga/commands/pipeline/` | Run a goga pipeline (or list them)   |
| `upgrade`   | `goga/commands/upgrade/`  | Upgrade goga and re-sync agents      |
| `install`   | `goga/commands/install/`  | Install a goga_tool_* package        |
| `uninstall` | `goga/commands/install/`  | Remove a goga_tool_* package         |
| `history`   | `goga/commands/history/`  | Work with the .goga/history/ tree    |
| `hooks`     | `goga/commands/hooks/`    | Inspect registered tool hooks        |
| `topics`    | `goga/commands/topics/`   | Topic board, creation, and switching |
| `runtime`   | `goga/commands/runtime/`  | Runtime state paths and archives     |
````

---

### 4. Cell `goga` (root) — CODEMANIFEST (modify)

Diff against the current `goga/CODEMANIFEST`:

**CHANGE** — in the `Imports:` block for `From: goga/commands`, add `runtime` to the
`Types` list (after `topics`):

```yaml
  - Types:
      - lint
      - build
      - connect
      - schema
      - codegraph
      - drift
      - contract
      - config
      - usages
      - tool
      - init
      - pipeline
      - upgrade
      - install
      - uninstall
      - history
      - hooks
      - topics
      - runtime
    Usages:
      - cli-commands
    From: goga/commands
```

**ADD** — in the `app()` type annotation's Commands list, the line `` - `runtime` ``
(after `` - `topics` ``).

**KEEP UNCHANGED** — the root `Usages:`, global `Annotations:`, the `->AST: {}`
embedding, the `AST` import, the footer.

**Usage file** `goga/.usages/domains.md` — no changes (the domain map covers domain
cells, not command subcells).

## Dependency Map

```
goga/runtime (modify)                         goga/docker (untouched)
      ▲                                             ▲
      │ Types: resolve_runtime_dir,                 │ Types: is_in_docker
      │        resolve_git_branch                   │
      │ Usages: runtime-paths                       │
      └──────────────┬──────────────────────────────┘
                     │
        goga/commands/runtime (create)
                     │ Types: runtime
                     │ Usages: path-queries, archive
                     ▼
          goga/commands (modify: Import + embedding)
                     │ Types: runtime (re-export with the 18 existing)
                     │ Usages: cli-commands
                     ▼
              goga (modify: app command table)
```

No cycles; `goga/runtime` remains a pure leaf; `goga/docker` is imported for the
`is_in_docker` fact only.

## Verification Checklist

After implementing each artifact, in order:

1. **`goga/runtime`**
   - `goga lint goga/runtime` passes (DSL rules: signature validity, reference
     resolution, usage links).
   - Existing consumers unchanged: `goga lint goga/commands/build` and
     `goga lint goga/commands/pipeline` still pass with no manifest edits there.
   - Behavior parity: `resolve_runtime_dir("builds")` output identical before/after
     the change (keyword-only parameter, default None).
2. **`goga/commands/runtime`**
   - `goga lint goga/commands/runtime` passes; every imported type and usage key is
     referenced (`ImportIsUsed`, `AllUsagesIsUsed`).
   - `.usages/path-queries.md` and `.usages/archive.md` exist (facade imports them in
     step 3 — the provider files must land first).
   - Facade check: `python -c "from goga.commands.runtime import runtime"`.
   - Per `convention`: tests in `tests/commands/runtime/` via `CliRunner`
     (single-line stdout, exit codes, in-image refusal with the `is_in_docker` mock,
     destination semantics, partial-archive removal).
3. **`goga/commands`**
   - `goga lint goga/commands` passes (embedding resolves; imported usages exist).
   - `goga schema` shows the new subcell with its dependencies on `goga/runtime` and
     `goga/docker`.
4. **`goga` (root)**
   - `goga lint .` passes project-wide; no cross-import cycles introduced.
   - `goga --help` lists `runtime`; bare `goga runtime` prints help, exit 0.
5. **Acceptance sweep** — run the acceptance criteria of `task.md` (SC1–SC10 plus the
   ADR-derived checks: dual `-b` parse, in-image refusal, strict destination
   semantics, no partial archives).
