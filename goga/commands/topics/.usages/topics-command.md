# commands/topics — the topics command group

Consumer scenarios of the `goga topics` command group. For users who
manage work as topics: boarding, creating, and switching; for the command
facade that registers the group.

The group scopes every subcommand to one year (--year/-y, default the
current year); the board subcommand reads remote-tracking refs with
--remote/-r and adds the todo column with --info/-i; the create subcommand
publishes fresh work without switching under --publish/-p.

## Boarding all work

    goga topics board
    goga topics --year 2025 board
    goga topics board --remote
    goga topics board --info

Prints a three-column table — topic, branch, statuses — with column and
row separators fitted to the terminal width. `--info/-i` adds the todo
column: topic, branch, todo, and statuses share the width — each of
the first three capped at a quarter of it minus the dividers — and the
todo cell shows the first line of the topic's `todo.md` that yields text
after leading `#` markers are stripped and the edges trimmed, read from the
ref trees without checkout (the current row from the working copy); a
topic without `todo.md` shows an empty cell. The todo column header is
`todo`. Overlong cells are truncated with an ellipsis. The current branch
row carries `*` in its topic cell; remote hosts keep their remote prefix.
A topic's statuses are all its maximal statuses, wrapped onto continuation
lines. An empty board prints nothing and exits 0.

## Creating fresh work

    goga topics create Feature/Foo_Bar
    goga topics --year 2025 create Feature/Foo_Bar
    goga topics create Feature/Foo_Bar -t "Payment retry"
    goga topics create Feature/Foo_Bar --todo "Fix retries.

    Retries ignore the backoff cap."
    goga topics create Feature/Foo_Bar -t

Creates the branch with the name as entered, switches to it, and creates
the topic directory of the scoped year. An explicit `--todo/-t` value
writes the topic todo file `todo.md` — the text as entered plus a
trailing newline, UTF-8; the todo may span multiple lines. `-t` without a
value (or with an empty one) starts the interactive multi-line entry:
type the todo line by line — empty lines continue the text as paragraphs —
and finish with a lone `.` line or Ctrl+D; the rule is stated in the
prompt. Entering nothing cancels the entry: no `todo.md` is written and
the command continues as without the flag. Interactive entry without a
terminal is a clean error. On the idempotent re-run (the current branch
already hosts the same slug) the topic directory is ensured and
`todo.md` is created or overwritten — nothing else mutates, no switch
happens. Without `-t` no todo file is written. Occupied names and empty
slugs trigger a re-ask on an interactive terminal, or a clean error with
a hint otherwise.

## Creating and publishing fresh work

    goga topics create Feature/Foo_Bar --publish -t "Payment retry"
    goga topics create Feature/Foo_Bar -p --todo
    goga topics create Feature/Foo_Bar -p -t "Payment retry" --base-ref origin/release-1.3
    goga topics create Feature/Foo_Bar -p -t "Payment retry" -c "chore: new topic {slug}"

Creates the branch off the configured base (topics.base_ref in
.goga/config.yml, overridden by --base-ref), commits the topic todo file
on it without touching the working copy — the caller stays on their
branch, a dirty tree and a detached HEAD are both fine — and pushes the
branch to origin with upstream binding. The topic is visible on the
remote board with the todo status. The result is one line: created and
published on the remote.

- The todo is required in this mode — the value comes from `--todo/-t` or
  the interactive entry.
- The commit message comes from topics.publish_commit (default
  `goga: create topic {slug}`), overridden by --commit/-c; the {slug}
  placeholder takes the topic slug, a template without it is used as is.
- An occupied name, an empty slug, or a slug already hosted by any branch
  of the inventory re-asks on an interactive terminal, or fails with a
  hint to the board.
- A failed publication rolls back fully — the branch is deleted and one
  clean error names the reason; re-run after fixing the cause succeeds.
- The base must come from --base-ref or the configuration — nothing set is
  a clean error with a configuration example; the base resolves as git
  resolves it, no fetch happens.
- --base-ref or --commit without --publish is a clean error; a missing
  origin or an unset git identity is a clean error.

## Switching to existing work

    goga topics switch history-com
    goga topics --year 2025 switch release-1-3-0

Resolves the identifier — exact branch name, then exact topic slug, then
prefixes — and switches. Several candidates offer a numbered list with
statuses; without interactive input the command fails with the list. Already
being on the host is an idempotent success. A dirty working tree is a clean
error when a mutation is needed. Switching is always local.

## Exit codes

Every subcommand exits 0 on success (an empty board included) and 1 on
error, with the error on stderr and no traceback.
