# history — goga history commands

The `goga history` command group works with the `.goga/history/` tree from
the command line. For script authors (workflow scripts, skill prompts) and
operators. A topic value can always be given as a branch name
(`release/1.3.0`) or as a slug (`release-1-3-0`) — both address
`.goga/history/<year>/release-1-3-0/`.

## Year addressing

The year is addressed by the group option `-y/--year` — given once, before
the subcommand, and shared by every subcommand:

    goga history -y 2025 status
    goga history --year 2025 ensure Feature/Foo_Bar

- Without the option (and an empty value counts as absent) every subcommand
  works with the current calendar year — except `list`, which prints the
  full tree.
- The value is a plain string; four digits is the documented grammar of a
  history year. `status`, `prune`, and `list` with a year missing from the
  tree print nothing and exit 0; `path` composes the path regardless —
  it never checks existence.
- A year option after the subcommand (`goga history status -y 2025`) is a
  usage error; so are a positional YEAR and any other year form.

## goga history list

Prints the inventory tree — every year with its topics, or the scoped year
alone. No statuses, no artifacts.

    2026/
     └── add-ref-for-review
     └── history-commands

- Read-only. An empty history prints nothing, exit 0.
- `goga history -y 2025 list` prints the 2025 section alone, same shape.

## goga history status [-t TOPIC] [-s STATUS]

    goga history status
    goga history -y 2025 status
    goga history status --topic release
    goga history status -s done -s mkdocs.published

Prints one line per topic of the scoped year: the slug and every maximal
status in brackets, in scale order — for example "release-1-3-0 [done]
[mkdocs.published]". Status filters take qualified status names: built-in
names bare, tool statuses as <tool>.<name>; a record matches when any of
its maximal statuses is one of the requested names. An unknown name is a
clean error. `-t/--topic` keeps the topics whose slug contains the
normalized filter as a substring; it combines with `-s/--status` by AND,
and a filter that normalizes to an empty slug is a clean error. The year
is never printed; an empty result prints nothing and exits 0.

## goga history path [TOPIC] [-f FILENAME]

Prints one path of the scoped year — and nothing else — to stdout. Nothing
is created.

    goga history path                           # topic dir of the current branch
    goga history path -f plan.md                # …/plan.md of the current branch
    goga history path release/1.3.0 -f plan.md  # explicit topic (branch name ok)
    goga history -y 2025 path                   # another year

- Without `TOPIC` the current git branch names the topic. No branch (not a
  repository, detached HEAD, git missing) → clean error, non-zero exit.
- `-f/--file` — an artifact filename with an extension; without the flag the
  topic directory is printed. A filename without an extension is an error.
- Scripting pattern: `plan=$(goga history path -f plan.md)`.

## goga history ensure [NAME]

Creates the topic directory of the scoped year — idempotently.

    goga history ensure                  # topic of the current branch
    goga history ensure Feature/Foo_Bar  # → .goga/history/<year>/feature-foo-bar
    goga history -y 2025 ensure fix-x    # → .goga/history/2025/fix-x

- An existing topic directory is a success, not a conflict. Occupancy
  checks belong to the caller.
- Prints nothing on stdout; the exit code carries the result.

## goga history prune [--dry-run]

Deletes the orphan topics of the scoped year — the topics no branch of the
repository inventory hosts — and prints one slug per line. Nothing else
is printed; an empty result prints nothing and exits 0.

    goga history prune --dry-run    # list the candidates, delete nothing
    goga history prune              # current year, delete the orphans
    goga history -y 2025 prune      # an explicit year

- Protection: a local branch or a remote-tracking ref whose short name
  normalizes to the topic slug protects the topic — in every year.
- Deletion is unconditional: no status protects a topic, the whole topic
  directory goes with all artifacts. The tree is not in git — a deleted
  topic directory is unrecoverable; run --dry-run first.
- Filesystem-only: branches, refs, and the index are never touched.

## Errors

Every failure is a clean message on stderr with a non-zero exit and no
fallback values: git unavailable / not a repository / detached HEAD, a
topic that normalizes to an empty slug, a filename without an extension, an
unknown status name, a tool package of the status scale that fails to
import (status), a topic directory that cannot be deleted (prune). Year
forms other than the group option — a positional YEAR, a year option after
the subcommand — are usage errors (non-zero exit, no traceback).
