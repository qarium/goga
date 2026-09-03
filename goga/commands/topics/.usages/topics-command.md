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

    goga topics create Feature/Foo_Bar --from-current
    goga topics create Feature/Foo_Bar --base-ref origin/main
    goga topics create Feature/Foo_Bar -t "Payment retry"
    goga topics --year 2025 create Feature/Foo_Bar --base-ref origin/main

Creates the branch off the base — --base-ref, topics.base_ref of
.goga/config.yml, or --from-current (the current HEAD); no base at all
is a clean error before anything else, naming the flag and the
configuration line. The preflight (an empty slug, an occupied branch
name or slug, the current branch hosting the same slug) runs before
the editor: creating the existing is an error with a hint to the
board — the todo of an existing topic is `goga topics switch ID
--todo`. An explicit --todo/-t value (only the value form exists; an
empty value counts as absent) is the todo; without a value a terminal
opens the external editor ($VISUAL/$EDITOR/vi) — an empty or unchanged
file cancels the entry and the command continues without a todo;
without a terminal and without a value the command is a clean error
naming --todo "...". The saved text becomes todo.md — the last action
of the normal path: the branch off the base, the switch, the topic
directory, then todo.md. On a terminal without --publish the
"Publish? [y/N]" ask appears only when a todo was obtained;
confirming publishes with a full rollback on failure, declining takes
the normal path.

## Creating and publishing fresh work

    goga topics create Feature/Foo_Bar --publish -t "Payment retry" --base-ref origin/main
    goga topics create Feature/Foo_Bar -p -t "Payment retry" -c "chore: new topic {slug}"

The publish path needs no terminal and asks nothing: the todo comes
from --todo/-t. The base comes from --base-ref, topics.base_ref, or
--from-current. --commit/-c (topics.publish_commit, default
`goga: create topic {slug}`) stays publication-only — an error without
--publish. A failed publication rolls back fully — the branch is
deleted and one clean error names the reason.

## Switching to existing work

    goga topics switch history-com
    goga topics switch history-com --todo

Resolves the identifier — exact branch name, exact topic slug, then
prefixes — and switches. Several candidates offer a numbered list with
statuses; without interactive input the command fails with the list.
Already being on the host is an idempotent success. A dirty working
tree is a clean error when a mutation is needed. With --todo the
editor opens with the topic's todo.md after the switch: saving
overwrites the file without a commit, cancelling leaves it untouched.
--todo on a branch without a topic, or without a terminal, is a clean
error before the switch. Switching is always local.

## Deleting topics

    goga topics delete feature-foo release-1-3-0
    goga topics delete feature-foo --yes

Resolves every identifier (branch name, topic slug, prefix — plus
topic directories of the year no branch hosts); an unknown or
ambiguous identifier cancels the whole call before anything is
removed. One confirmation for the whole list — "Delete N topics?
[y/N]" with the topic-to-branch pairs; --yes/-y skips it (a
non-terminal without --yes is a clean error; the -y collision with the
group --year is resolved by position). The deletion is symmetric to
creation-and-publication: the local branch and its origin twin are
both removed (the local first; a failed remote deletion restores the
local branch and stops with one clean error), and the topic directory
joins the deletion of every target — branches or none. The current
branch hosting a target is a clean error — switch away first. Merged
work is out of scope: a topic hosted only by branches that are not its
own topic branch is a clean error naming the hosting branch; a topic
carried by both its own branch and a merged-work host deletes its
eligible refs but keeps its directory — the merged host's tree
survives. Unmerged commits never block: the deletion is unconditional
after the confirmation.

## Exit codes

Every subcommand exits 0 on success (an empty board included) and 1 on
error, with the error on stderr and no traceback.
