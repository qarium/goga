# commands/topics — the topics command group

Consumer scenarios of the `goga topics` command group. For users who
manage work as topics: boarding, creating, and switching; for the command
facade that registers the group.

The group scopes every subcommand to one year (--year/-y, default the
current year); the status subcommand reads remote-tracking refs with
--remote/-r and adds the title column with --info/-i.

## Boarding all work

    goga topics status
    goga topics --year 2025 status
    goga topics status --remote
    goga topics status --info

Prints a three-column table — topic, branch, statuses — with column and
row separators fitted to the terminal width. `--info/-i` adds the title
column: topic, branch, title, and statuses share the width — each of
the first three capped at a quarter of it minus the dividers — and the
title shows the first line of the topic's `title.txt`, read from the
ref trees without checkout (the current row from the working copy); a
topic without a title file shows an empty cell. Overlong cells are
truncated with an ellipsis. The current branch row carries `*` in its
topic cell; remote hosts keep their remote prefix. A topic's statuses
are all its maximal statuses, wrapped onto continuation lines.
An empty board prints nothing and exits 0.

## Creating fresh work

    goga topics create Feature/Foo_Bar
    goga topics --year 2025 create Feature/Foo_Bar
    goga topics create Feature/Foo_Bar -t "Payment retry"

Creates the branch with the name as entered, switches to it, and creates
the topic directory of the scoped year. An explicit `--title/-t` also
writes the topic title file `title.txt` — the text as entered plus a
trailing newline; on the idempotent re-run (the current branch already
hosts the same slug) the topic directory is ensured and the title file
is created or overwritten — nothing else mutates, no switch happens.
Without `-t` no title file is written. Occupied
names and empty slugs trigger a re-ask on an interactive terminal, or a
clean error with a hint otherwise.

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
