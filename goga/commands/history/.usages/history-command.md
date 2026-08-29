# history — goga history commands

The `goga history` command group works with the `.goga/history/` tree from
the command line. For script authors (workflow scripts, skill prompts) and
operators. A topic value can always be given as a branch name
(`release/1.3.0`) or as a slug (`release-1-3-0`) — both address
`.goga/history/<year>/release-1-3-0/`.

## goga history list

Prints the inventory tree — every year with its topics. No statuses, no
artifacts.

    2026/
     └── add-ref-for-review
     └── history-commands

- Read-only. An empty history prints nothing, exit 0.

## Reading the statuses of a year

    goga history status
    goga history status 2025
    goga history status --topic release
    goga history status -s done -s mkdocs.published

Prints one line per topic: the slug and every maximal status in brackets,
in scale order — for example "release-1-3-0 [done] [mkdocs.published]".
Status filters take qualified status names: built-in names bare, tool
statuses as <tool>.<name>; a record matches when any of its maximal
statuses is one of the requested names. An unknown name is a clean error.
The year is never printed; an empty result prints nothing and exits 0.

## goga history path [TOPIC] [-f FILENAME] [-y YEAR]

Prints one path — and nothing else — to stdout. Nothing is created.

    goga history path                           # topic dir of the current branch
    goga history path -f plan.md                # …/plan.md of the current branch
    goga history path release/1.3.0 -f plan.md   # explicit topic (branch name ok)
    goga history path -y 2025                   # another year

- Without `TOPIC` the current git branch names the topic. No branch (not a
  repository, detached HEAD, git missing) → clean error, non-zero exit.
- `-f/--file` — an artifact filename with an extension; without the flag the
  topic directory is printed. A filename without an extension is an error.
- `-y/--year` — four digits; defaults to the current year.
- Scripting pattern: `plan=$(goga history path -f plan.md)`.

## goga history ensure [NAME]

Creates the topic directory of the current year — idempotently.

    goga history ensure                  # topic of the current branch
    goga history ensure Feature/Foo_Bar  # → .goga/history/<year>/feature-foo-bar

- An existing topic directory is a success, not a conflict. Occupancy
  checks belong to the caller.
- Prints nothing on stdout; the exit code carries the result.

## Errors

Every failure is a clean message on stderr with a non-zero exit and no
fallback values: git unavailable / not a repository / detached HEAD, a
topic that normalizes to an empty slug, a filename without an extension, an
unknown status name.
