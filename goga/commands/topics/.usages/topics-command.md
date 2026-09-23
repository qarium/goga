# commands/topics — the topics command group

Consumer scenarios of the `goga topics` command group. For users who
manage work as topics: boarding, creating, and switching; for the
command facade that registers the group.

The group scopes every subcommand to one year (--year/-y, default the
current year); the board subcommand reads remote-tracking refs with
--remote/-r, adds the todo column with --info/-i, filters by hosting
branch with the repeatable --host, switches to the expanded per-host
audit view with --per-host, and prints machine-readable records with
--json; the create subcommand creates fresh work without switching by
default, switches under --switch/-s, and publishes under --publish/-p;
--todo/-t takes a value, or no value to read the todo from stdin.

## Boarding all work

    goga topics board
    goga topics --year 2025 board
    goga topics board --remote
    goga topics board --info
    goga topics board --host main --host release/1.3

The default board shows exactly one entry per topic of the scoped
year that still has its own branch — the hosting branch whose branch
part (the whole name of a local branch, the short name of a
remote-tracking ref) normalizes into the topic slug; a
remote-tracking ref qualifies, so remote-only topics keep their
entry; a topic whose history survives only in merged hosts shows no
entry (--per-host keeps its rows). The table columns are topic,
branch, hosts, todo (--info), statuses. The branch column shows the
own branch —
several colliding own branches resolve deterministically (the
current branch, else a local branch over a remote-tracking one, else
the alphabet). The hosts column lists every branch carrying the
topic's history, the own branch included, alphabetical; entries wrap
onto continuation lines. The statuses are the own branch's maximal
statuses — artifacts that exist solely on merged hosts do not advance
them. The current branch's entry carries `*`. The todo cell shows the
first line of the topic's `todo.md` that yields text after leading
`#` markers are stripped and the edges trimmed; a topic without
`todo.md` shows an empty cell. An empty board prints nothing and
exits 0. Reading is strictly read-only — no checkout, no fetch, no
mutation.

--host NAME (repeatable) filters by exact hosting-branch display
name; several values unite. In the default view the entries whose
hosts list contains any given name stay — an own branch is still
required, the filter never resurrects a hidden topic. In the per-host
view the rows of the named hosts stay. An unknown name leaves an
empty board (or [] under --json) with exit 0 — never an error.

## Auditing every hosting branch

    goga topics board --per-host
    goga topics board --per-host --info

--per-host switches to the expanded audit view: one row per topic and
hosting branch, showing that branch's own statuses — complete
including topics without an own branch. The table keeps the
established layout (topic, branch, statuses; the todo column under
--info); the current marker applies per hosting branch, the remote
marker per ref, and a local branch still absorbs its remote twin.

## Consuming the board as JSON

    goga topics board --json
    goga topics board --json --remote
    goga topics board --per-host --json

--json prints the board as a pretty-printed JSON array. Default
records carry exactly the fields topic, branch, hosts, statuses,
current, remote, todo — todo is a string or null. Per-host records
carry topic, branch, statuses, current, remote, todo — no hosts. The
year scoping and --remote apply exactly as to the table. An empty
board prints []. --json --info is a clean error — the todo is always
present in JSON. The field names and record shapes are a stable
contract for external tools; the key order is not.

## Creating fresh work

    goga topics create Feature/Foo_Bar --from-current
    goga topics create Feature/Foo_Bar --base-ref origin/main
    goga topics create Feature/Foo_Bar -t "Payment retry"
    printf 'First line\nSecond line\n' | goga topics create Feature/Foo_Bar --todo --from-current
    goga topics create Feature/Foo_Bar -s
    goga topics --year 2025 create Feature/Foo_Bar --base-ref origin/main

Creates the branch off the base — --base-ref, topics.base_ref of
.goga/config.yml, or --from-current (the current HEAD); no base at
all is a clean error before anything else, naming the flag and the
configuration line. The preflight (an empty slug, an occupied branch
name or slug, the current branch hosting the same slug) runs before
any todo source: creating the existing is an error with a hint to the
board — the todo of an existing topic is `goga topics switch ID
--todo`.

The --todo/-t option takes an optional value. With a value it is the
todo (an empty value counts as absent). Without a value it declares
stdin as the source: pipe the multi-line todo in and it becomes the
todo — no editor opens, nothing is asked, and the publication ask
never appears. Without the option, a terminal opens the external
editor ($VISUAL/$EDITOR/vi) — an empty or unchanged file cancels the
entry; without a terminal and without a value the command is a clean
error naming --todo "...". Piping content while declaring no source
(neither a value nor the value-less --todo) is a clean error naming
--todo — piped content is never silently ignored; piping bytes that
are not UTF-8 with the value-less --todo is the same clean error. A
terminal stdin is never read; a pipe is read fully exactly once, at
todo-resolution time. The stdin todo works on every creation path —
the default, --switch/-s, and --publish/-p.

By default the resolved text becomes one quarantined commit —
todo.md on top of the base — and the branch is planted at it: you
stay on your branch, nothing lands in the working copy, and the todo
is required. --switch/-s checks out the fresh branch instead — the
topic directory and todo.md appear in the working copy uncommitted,
and the todo is optional; --switch acts only without --publish. On a
terminal without --publish the "Publish the branch to origin? [y/N]"
ask appears only when a todo was obtained and did not come from
stdin; confirming publishes with a full rollback on failure, declining
takes the local path.

## Creating and publishing fresh work

    goga topics create Feature/Foo_Bar --publish -t "Payment retry" --base-ref origin/main
    goga topics create Feature/Foo_Bar -p -t "Payment retry" -c "chore: new topic {slug}"

The publish path needs no terminal and asks nothing: the todo comes
from --todo/-t or the piped stdin under the value-less form. The base
comes from --base-ref, topics.base_ref, or --from-current. --commit/-c
(topics.publish_commit, default `goga: create topic {slug}`) stays
publication-only — an error without --publish. A failed publication
rolls back fully — the branch is deleted and one clean error names
the reason.

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

Every subcommand exits 0 on success (an empty board and [] included)
and 1 on error, with the error on stderr and no traceback.
