# goga topics

Work with the topics of one year — the cross-branch inventory, fresh-work creation, switching, deletion, and the merged-topic clear.

`goga topics` is a Click group with five subcommands (`board`, `create`, `switch`, `delete`, `clear`) over the topics domain. It is host-side and git-driven: the board and the deletion and clear resolutions read branch trees without checkout, and creation and switching perform bounded local git mutations. The only network operations are the `--publish` push and the delete push (one per target that has an origin twin — `delete` and `clear` share it); no fetch ever happens; every other mutation is local.

## Synopsis

```bash
goga topics [--year YYYY] board [--remote] [--info] [--host NAME]... [--topic SLUG]... [--per-host] [--json]
goga topics [--year YYYY] create BRANCH_NAME [--todo [TEXT]] [--switch] [--publish] [--base-ref REF] [--from-current] [--commit TEMPLATE]
goga topics [--year YYYY] switch IDENTIFIER [--todo]
goga topics [--year YYYY] delete IDENTIFIER... [--yes]
goga topics [--year YYYY] clear [--base-ref REF] [--yes]
```

`--year`/`-y` scopes every subcommand to one four-digit year (default: the current year). The year is never printed.

## `goga topics board`

Prints the board — the cross-branch topic inventory of the scoped year — in two views over one collection pass.

The default view is a four-column table — topic, branch, hosts, statuses — with one entry per topic that still has its own branch:

```
| Topic          | Branch         | Hosts          | Statuses
|----------------|----------------|----------------|-------------------
| feat-b         | feat-b         | feat-b         | [defined]
|----------------|----------------|----------------|-------------------
| * feat-a       | feat-a         | feat-a         | [planned]
|                |                | feat-b         |
|----------------|----------------|----------------|-------------------
```

- One entry per topic with an **own branch** — a hosting branch whose branch part (the whole name of a local branch, the short name of a remote-tracking ref) normalizes into the topic slug. A topic carried only by merged hosts — a topic without its own branch — appears in no view, default, audit, and JSON alike; it is history, reachable through git itself.
- The **hosts** column lists every branch carrying the topic's history — the own branch included — alphabetical by display name; a local branch and its remote twin count as one host under the local name. Every host name prints on its own grid line of the column — a name never splits, an overlong one truncates with an ellipsis.
- Several own branches colliding resolves deterministically: the record hosting the current branch, otherwise a non-remote record over a remote-tracking one, otherwise the display-name alphabet. The entry carries that record's statuses and todo summary.
- `*` marks the entry whose own branch is the current working branch — a merged host carrying the topic's history never carries the marker.
- The record of the current branch reads the working copy — uncommitted progress is visible; every other record reads its branch's committed tree (no checkout happens).
- Entries sort by scale order of the first maximal status, then alphabetically by topic.
- `--per-host` switches to the **audit view** — the three-column table (topic, branch, statuses) with one row per topic and hosting branch of the own-branched topics, the pre-aggregation records verbatim: every hosting branch of a kept topic gets its own row.
- `--host NAME` keeps only the named hosting branches — an exact display-name match, repeatable, the union across values. The default view filters the entries whose hosts list contains a given name; the audit view filters the records by branch display name. An unknown name is the empty board, never an error.
- `--topic SLUG` keeps only the named topics — an exact slug match, repeatable, the union across values, composed with `--host` (an entry or row survives both filters). The own-branch requirement stands first: a filter never resurrects a topic without its own branch. An unknown slug is the empty board, never an error.
- `--remote`/`-r` reads remote-tracking refs instead of local branches; the current branch shows through its remote twin.
- `--info`/`-i` adds the todo column — between hosts and statuses in the default view, between branch and statuses in the audit view — the first line of the topic's `todo.md` that yields text after leading `#` markers are stripped and the edges trimmed; a topic without a `todo.md`, or one whose every line reduces to emptiness, renders an empty cell. The working copy reads the file directly; every other row reads it from the branch's tree (no checkout).
- `--json` prints the machine-readable projection of either view instead of the table — a pretty-printed JSON array (indent 4, sorted keys, UTF-8; `[]` for an empty board). Every item carries `topic`, `branch`, `statuses`, `current`, `remote`, and `todo` (a string or `null`, never omitted); the default view's items carry `hosts` too. `--json` cannot combine with `--info` — a clean error before any git access.
- A row divider — the same dash run as under the header — closes every entry, the last included; wrapped continuation lines stay undivided.
- Every host name prints on its own continuation line of the hosts column; the statuses wrap onto continuation lines when the segments overflow the terminal width. The table never exceeds the width except on terminals below the narrow threshold of the active column rule — 44 columns for the four-column default table, 55 with `--info`, 33 for the three-column audit table, 44 with its `--info` — where every column keeps a minimum of 8.
- An empty board prints nothing as a table, `[]` as JSON, and exits 0 — a year without topics is not an error.

The statuses are the topic's **maximal present statuses** in scale order — `empty, todo, defined, discovered, backlog, designed, specified, planned, done`, deepening as `todo.md`, `prd.md`, `adr.md`, `task.md`, `arch.md`, `design.md`, `plan.md`, and `completed/plan.md` land. Tool packages can add their own statuses, shown qualified (`mkdocs.published`); see [Tools](../tools/index.md).

## `goga topics create`

Creates fresh work — a branch named exactly as entered, planted at a base commit with the topic of the scoped year committed on it, while you stay on your branch:

```bash
goga topics create Feature/Foo_Bar --from-current --todo "Payment retry"
# Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar
# (one commit on the branch carries .goga/history/2026/feature-foo-bar/todo.md;
#  the working copy, the index, and HEAD stay untouched — no switch)

goga topics create Feature/Foo_Bar --base-ref origin/main --switch
# Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar
# (the branch is checked out; .goga/history/2026/feature-foo-bar/ now exists
#  in the working copy; on a terminal the publication ask appears first)
```

- The branch name is taken verbatim; git itself rejects invalid names. The default path builds one quarantined commit carrying the topic's `todo.md` on top of the resolved base commit — git plumbing that never touches the working copy, so a dirty tree and a detached HEAD do not interfere — and plants the branch at it (`git update-ref --stdin`); no switch happens, and `goga topics switch <name>` brings you onto the work later. `-s`/`--switch` plants the branch at the base and checks it out instead (`git switch`) — a failed checkout rolls the planted branch back so the name never strands — with the topic directory created in the working copy, uncommitted.
- The base resolves as `--base-ref` > `topics.base_ref` in `.goga/config.yml` > the current HEAD under `--from-current` > clean error. With nothing set, exit 1 with a message naming the flag, the flag alternative, and the configuration line, including a two-line YAML example (see [Configuration](configuration.md)).
- The topic directory is `.goga/history/<YYYY>/<slug>/`, where the slug is the normalized name (lowercase, non-ASCII dropped, anything outside `[a-z0-9]` as `-`, repeat hyphens collapsed, edges trimmed: `Feature/Foo_Bar` → `feature-foo-bar`). The default path carries the directory as the committed `todo.md`; `--switch` creates it on disk. No artifact file is written unless a todo resolves.
- `-t`/`--todo` carries three states: a value is the todo itself — the multi-line text as entered plus one trailing newline, UTF-8 — which marks the topic `todo` on the status scale and feeds the `--info` column of the board; the value-less form declares the piped stdin as the todo source (see [Editor todo entry](#editor-todo-entry)); an empty value — `--todo ""`, `--todo=`, `-t ""` — counts as absent: no `todo.md` is ever created empty. The literal `__declared__` is the reserved marker of the stdin declaration.
- The todo is **required** on the default path — git keeps no empty directories, so the work exists only through its committed `todo.md`. A cancelled editor entry or a missing todo exits 1 with `the local creation needs a todo — the board reads the topic through todo.md; pass --todo/-t with a value, or pipe the todo into stdin and pass the value-less --todo, or --switch/-s to create on the spot without one`. Under `--switch` the todo is optional.
- `--switch` acts only without `--publish` — the publication never switches, so the two together are a clean error (exit 1).
- The current branch already hosting the same slug is a clean error (exit 1) — `branch <name> already hosts topic <YYYY>/<slug> — switch to it instead of re-creating it`. There is no idempotent path.
- Occupancy is probed against three oracles in order: a local branch with the entered name, a remote-tracking branch with the entered name (local refs only — no network), and an existing `.goga/history/<YYYY>/<slug>/` directory (only a directory occupies a topic). A fourth oracle applies to every creation: any branch tree of the inventory — local and remote-tracking refs — hosting the topic directory of the slug (`topic '<slug>' of <YYYY> is already hosted by branch '<branch>'`).
- An occupied name, an unresolvable base, or a name that normalizes to an empty slug (a fully non-ASCII name) is one clean error (exit 1) with the reason and a hint to `goga topics board` for occupied names — there is no re-ask. Every read-only decision (the preflight) runs before the first input, so a failing base never wastes an entered todo.

### Editor todo entry

The todo resolves through an acquisition ladder: a given value, else the declared piped stdin, else the external editor on an interactive terminal, else nothing — and the path rules decide (the default path and `--publish` need a todo, `--switch` does not).

```
$ printf 'Pay the retry cap.\n' | goga topics create feat/x --from-current --todo
# Created branch feat/x and topic 2026/feat-x
# (the piped content becomes the todo verbatim; no ask follows — a piped
#  todo is a scripted creation)

$ goga topics create feat/x --from-current --switch
Enter the text. An empty or unchanged file cancels the entry.
# (the editor opens; saving writes todo.md, cancelling leaves nothing)
# Created branch feat/x and topic 2026/feat-x
```

- The value-less `--todo`/`-t` declares the piped stdin as the todo source: the pipe is read fully exactly once at todo-resolution time — after the read-only preflight, before the editor and the ask — decoded strictly as UTF-8 (anything else is a clean error naming the option, exit 1) and never trimmed; its content becomes the todo verbatim with the value-form semantics. The read happens only on this rung — the value form never touches the pipe.
- Content on the pipe without the declaration is never silently ignored — it is a clean error naming the option (exit 1): `stdin carries content but no todo source is declared — pass --todo/-t with a value or the value-less --todo to read the piped content`. A bare pipe — declared or not — falls through to the editor rung.
- The editor rung opens only on an interactive terminal; the editor resolves through `$VISUAL` → `$EDITOR` → the system default (`vi`), the session editing a temporary file outside the project.
- Saving a blank file — or a file unchanged from its prefill — cancels the entry: under `--switch` the command continues with no `todo.md` written; on the default path the creation is a clean error asking for the todo (see above). A failed editor run is a clean error with nothing mutated.
- Without an interactive terminal and with no todo resolved: the default path and `--publish` fail with their path-specific clean errors (exit 1), while a headless `--switch`/`-s` creation succeeds with no todo at all.

### The publication ask

On an interactive terminal, without `--publish`, once a todo is resolved, the command asks once: `Publish the branch to origin?` — never when the todo came from the pipe (a piped todo is a scripted creation). An empty answer reads the default no — the local path runs (the quarantined branch, or the checked-out branch under `--switch`); answering yes takes the publication path below; Ctrl-C or EOF aborts with nothing created. Without a terminal, or with a cancelled todo entry, no ask happens and the local path runs.

### `--publish` — create and publish in one step

`-p`/`--publish` takes the publication path without the ask: it builds the branch off the resolved base, commits only the topic's `todo.md` on it, and pushes it to `origin` — while you stay on your branch:

```bash
goga topics create Feature/Foo_Bar --publish --todo "Payment retry"
# Created branch Feature/Foo_Bar and published topic 2026/feature-foo-bar
```

- The working copy, the index, and HEAD stay untouched — the commit is built through quarantined git plumbing, so a dirty tree and a detached HEAD do not interfere; the topic directory is never created on disk.
- The branch carries exactly one commit — the todo file at `.goga/history/<YYYY>/<slug>/todo.md` — and is pushed to `origin` with upstream binding (`git push -u`, exactly that one branch). The topic appears on the remote board with the `todo` status.
- A todo is **required** under `--publish` (the board reads the topic through the todo file). An omitted `--todo` resolves through the acquisition ladder first — the piped stdin under the value-less declaration, else the editor; a missing or cancelled todo exits 1 with `the publication needs a todo — the board reads the topic through todo.md`.
- Commit template: `--commit`/`-c` > `topics.publish_commit` > the built-in default `goga: create topic {slug}`. `{slug}` is replaced with the topic slug; a template without the placeholder is used verbatim. `--commit` without `--publish` is a clean error (exit 1) — it acts only together with `--publish`.
- `origin` must be configured (exit 1 otherwise, before any mutation). The repository git identity must be set — `commit-tree` needs an author.
- A failed push rolls back fully: the planted branch is deleted, nothing else was ever mutated, and git's push reason surfaces as one clean error (`git failed: <git stderr>`, exit 1). A re-run with the same name then succeeds.

## `goga topics switch`

Brings the repository onto the branch hosting the requested work:

```bash
goga topics switch feat-x
# Switched to branch feat/x

goga topics switch feat-x --todo
# Switched to branch feat/x
# (the editor opens with the topic's todo.md; saving overwrites it, no commit)
```

IDENTIFIER resolves through three tiers — the first tier with a match wins, so a unique identifier never reaches a prompt:

1. exact branch name;
2. exact topic slug (local branches before remote-tracking refs);
3. prefix — a branch whose name, or whose hosted slug, starts with the input.

- Several candidates on an interactive terminal: the numbered list with each candidate's statuses is printed and a number is prompted; with no terminal, the numbered list itself is the error (exit 1).
- No candidate at all: exit 1 with a hint to run `goga topics board`.
- Already on the hosting branch: idempotent success — `Already on branch <name>` — with no working-tree probe and no mutation.
- A local host is checked out (`git switch <branch>`); a remote-only host creates the local branch from the remote-tracking ref (`git switch -c <branch> <remote>/<branch>`, reported as `Created branch <branch> from <remote>/<branch>`).
- A switch that would mutate first probes the working tree; a dirty tree exits 1 with `working tree is dirty — commit or stash before switching` before anything is touched.

### `--todo` — enter the topic's todo after the switch

With `--todo` the external editor opens with the switched topic's `todo.md` after the switch — the same editor session as the create entry, prefilled with the existing todo. Saving overwrites the file as entered plus one trailing newline, without a commit; cancelling (no save, blank, or unchanged) leaves it untouched.

- The flag needs an interactive terminal — without one it is a clean error before any resolution (exit 1).
- The chosen candidate must host a topic — `branch '<name>' hosts no topic — switching creates nothing` (exit 1); switching never creates anything.
- Already sitting on the hosting branch still enters the todo — the idempotent switch carries the entry.

The same resolution backs the switch half of `goga pipeline <name> -t <identifier>` — there, an identifier nothing hosts creates fresh work instead of failing, and a sibling `--todo` flag opens the same entry (see [pipeline](../pipelines/cli.md#topic-switch)).

## `goga topics delete`

Deletes identified topics — the local branch, its origin twin, and the topic directory:

```bash
goga topics delete feature-foo
# feature-foo -> Feature/Foo_Bar
# Delete 1 topic(s)? y
# Deleted 1 topic(s) of 2026: feature-foo

goga topics delete feature-foo feature-bar --yes
# Deleted 2 topic(s) of 2026: feature-foo, feature-bar
```

Every IDENTIFIER resolves first — a branch name, a topic slug, or their prefix (the same tier order as `switch`), plus topic directories of the year no branch hosts:

- An identifier nothing hosts, an ambiguous identifier, a topic without its own branch, several branches hosting one topic, or the current branch hosting a target is a clean error (exit 1) and nothing is deleted — the resolution is all-or-nothing.
- A local branch and its `origin` twin collapse into one target; repeated identifiers naming one topic collapse too. A tracking ref of another remote is not a twin — the deletion push targets `origin` only. Two local branches normalizing into one slug (say `Feature/Foo` and `feature-foo`) never pick one of them by order — `several branches host topic '<topic>': <branches> — remove all but one of them before deleting`.
- A topic exists exactly as long as its own branch exists: the own branch is found **by name** — a ref whose branch part (the whole name of a local branch, the short name of a remote-tracking ref) normalizes into the topic slug — never by tree carriage. A topic without its own branch — its history hosted by other branches only, the post-merge state — is a clean error naming no hosting branch: `topic '<topic>' has no branch — there is nothing to delete; it is history`. A topic directory no branch hosts stays deletable (directory only) — an unpublished topic (its todo not yet committed) reaches its disk directory by its exact name, and the bare same-named branch is the topic's own branch by name: it goes with the topic.
- The resolved list prints one line per target — `<topic> -> <branch>` (or the twin, or `(directory only)`) — and one confirmation covers the whole list; a declined answer exits 0 with nothing deleted. `--yes`/`-y` skips the confirmation; without it a non-interactive terminal is a clean error naming the flag.
- The removal deletes each topic's own local branch, its `origin` twin (a network push), and its topic directory — the directory joins the deletion exactly when no branch surviving the deletion carries the topic (the survivors are the inventory minus the target's own branch and twin; the own branch's own tree dies with it, a non-`origin` own-named tracking ref survives and keeps the directory). The current branch hosting a target — by branch name or by slug — is a clean error asking to switch away first.
- A rejected remote deletion restores the failing target's local branch at its captured commit and surfaces git's reason as one clean error; targets removed before the failure stay removed.

## `goga topics clear`

Clears the merged topics of the scoped year — every own-branched topic whose topic directory the base ref's tree carries:

```bash
goga topics clear
# feature-foo -> feature-foo
# feature-bar -> feature-bar
# Clear 2 topic(s)? y
# Deleted 2 topic(s) of 2026: feature-foo, feature-bar

goga topics clear --base-ref origin/release/2.0.0 --yes
# Deleted 1 topic(s) of 2026: feature-foo
```

- The base resolves as `--base-ref` > `topics.base_ref` in `.goga/config.yml` — there is no current-HEAD rung, unlike `create`; no base at all is a clean error naming the flag and the configuration line (exit 1). The base is any revision string git resolves (a branch, a remote-tracking ref, a tag, a hash); it is resolved once, read at the resolved commit, and never moved or pushed — being on it is not an error.
- The scope is every topic of the year that still has its own branch and whose topic directory the base tree carries — the merged topics of the year. A branchless topic is out of scope silently — it is history. An empty scope prints `No merged topics to clear.` and exits 0 — not an error.
- The resolved list prints one line per target — `<topic> -> <branch>` (or the twin, or `(directory only)`) — and one confirmation (`Clear N topic(s)?`) covers the whole list; a declined answer exits 0 with nothing deleted. `--yes`/`-y` skips the confirmation; without it a non-interactive terminal is a clean error naming the flag (the `-y` sits after the subcommand token, unlike the group `-y` year).
- Deletion semantics are exactly those of [`goga topics delete`](#goga-topics-delete): the own local branch, the `origin` twin, and the survivor-gated directory of each target go in one confirmed pass, a rejected remote deletion restores the local branch at its captured commit, and `topic_deleted` fires per fully removed target. Only the targets' own refs are touched — the other hosts of a target are not.
- The current branch being a target's own branch — by branch name or by slug — is a clean error asking to switch away first; the whole clear cancels.

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success — the board printed, the work created or published, the switch performed, the deletion or clear done (including the idempotent switch, a declined deletion or clear, and an empty clear scope) |
| `1` | A clean domain error: an unresolvable or ambiguous identifier, no base for a creation or a clear, an unresolvable clear base, an occupied name, a missing todo under `--publish` or the no-switch creation, `--switch` together with `--publish`, a dirty working tree, a branchless (no-own-branch) deletion target or the current branch hosting one, a failed publication or remote deletion, a git infrastructure failure, or a broken `goga_tool_*` package failing to import during status-scale or hooks-registry assembly |
| `2` | A usage error (unknown option, missing argument) |

## Notes

- Every mutation is local except the two `origin` pushes — the `--publish` push and the delete push (`delete` and `clear` share it); no fetch ever happens.
- `goga history status` shows the same statuses scoped to the working copy of one year (see [history](../history/cli.md)).
