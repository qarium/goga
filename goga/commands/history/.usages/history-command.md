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

## goga history status [YEAR] [-t TOPIC] [-s STATUS]…

Prints one `topic [status]` line per topic of the year — flat, no year, no
tree.

    release-1-3-0 [done]
    history-commands [planned]

- `YEAR` — optional positional, four digits; defaults to the current year.
- `-t/--topic` — substring filter; the value is normalized (a branch name
  works as a filter too). A `--topic` value that normalizes to an empty slug
  (fully non-ASCII) is an error, not a match-all.
- `-s/--status` — repeatable (`-s defined -s discovered`); combined with
  `--topic` by AND. Valid names: `empty`, `defined`, `discovered`,
  `backlog`, `designed`, `specified`, `planned`, `done`. An unknown name is
  an error (non-zero exit).
- Topics come out alphabetically. An empty result prints nothing, exit 0.
- Statuses are colorized on a terminal; piped output is plain; `NO_COLOR`
  disables color always.

A topic's status is the deepest artifact present: `prd.md` → defined,
`adr.md` → discovered, `task.md` → backlog, `arch.md` → designed,
`design.md` → specified, `plan.md` → planned, `completed/plan.md` → done;
no artifacts → empty.

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
