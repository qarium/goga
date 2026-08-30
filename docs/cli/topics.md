# goga topics

Work with the topics of one year — the cross-branch inventory, fresh-work creation, and switching.

`goga topics` is a Click group with three subcommands (`status`, `create`, `switch`) over the topics domain. It is host-side and git-driven: the board reads branch trees without checkout, and creation and switching perform bounded local git mutations. `create --publish` is the one exception on the network: it pushes the branch to `origin` (the only network operation of the group — no fetch ever happens); every other mutation is local.

## Synopsis

```bash
goga topics [--year YYYY] status [--remote] [--info]
goga topics [--year YYYY] create BRANCH_NAME [--title TITLE] [--publish] [--base-ref REF] [--commit TEMPLATE]
goga topics [--year YYYY] switch IDENTIFIER
```

`--year`/`-y` scopes every subcommand to one four-digit year (default: the current year). The year is never printed.

## `goga topics status`

Prints the board — the cross-branch topic inventory of the scoped year — as a three-column table: topic, branch, statuses.

```
| Topic          | Branch   | Statuses          |
|----------------|----------|-------------------|
| feat-b         | feat-b   | [defined]         |
| * feat-a       | feat-a   | [planned]         |
| feat-a         | feat-b   | [planned]         |
```

- One row per topic hosted by a branch; `*` marks the row hosting the current branch.
- The current branch's row reads the working copy — uncommitted progress is visible; every other row reads the branch's committed tree (no checkout happens).
- A local branch and its remote twin collapse to one row — the local branch wins; a topic hosted only by a remote-tracking ref keeps its row with the remote name in the branch column.
- Rows sort by scale order of the first maximal status, then alphabetically by topic.
- `--remote`/`-r` reads remote-tracking refs instead of local branches; the current branch shows through its remote twin.
- `--info`/`-i` adds the title column between branch and statuses — the first line of the topic's `title.txt`, an empty cell when the topic has none. The working copy reads the file directly; every other row reads it from the branch's tree (no checkout).
- The statuses column wraps onto continuation lines when the segments overflow the terminal width; the table never exceeds the width except on terminals below the narrow threshold of the active column rule — 33 columns for the three-column table, 44 with `--info` — where every column keeps a minimum of 8.
- An empty board prints nothing and exits 0 — a year without topics is not an error.

The statuses are the topic's **maximal present statuses** in scale order — `empty, new, defined, discovered, backlog, designed, specified, planned, done`, deepening as `title.txt`, `prd.md`, `adr.md`, `task.md`, `arch.md`, `design.md`, `plan.md`, and `completed/plan.md` land. Tool packages can add their own statuses, shown qualified (`mkdocs.published`); see [Tools](../tools.md).

## `goga topics create`

Creates fresh work — a branch named exactly as entered, plus the topic directory of the scoped year:

```bash
goga topics create Feature/Foo_Bar
# Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar

goga topics create Feature/Foo_Bar --title "Payment retry"
# Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar
# (.goga/history/2026/feature-foo-bar/title.txt now carries "Payment retry")
```

- The branch name is taken verbatim (`git switch -c`); git itself rejects invalid names.
- The topic directory is `.goga/history/<YYYY>/<slug>/`, where the slug is the normalized name (lowercase, non-ASCII dropped, anything outside `[a-z0-9]` as `-`, repeat hyphens collapsed, edges trimmed: `Feature/Foo_Bar` → `feature-foo-bar`). No artifact file is written unless `--title` is given.
- `-t`/`--title` writes the topic title file `title.txt` in the topic directory — the title as entered plus one trailing newline, UTF-8 — which marks the topic `new` on the status scale and feeds the `--info` column of the board.
- The current branch already hosting the same slug is an idempotent success — `Branch <name> already hosts topic <YYYY>/<slug>` — with nothing touched, except that an explicit `--title` creates or overwrites the title file.
- Occupancy is probed against three oracles in order: a local branch with the entered name, a remote-tracking branch with the entered name (local refs only — no network), and an existing `.goga/history/<YYYY>/<slug>/` directory (only a directory occupies a topic).
- An occupied name or a name that normalizes to an empty slug (a fully non-ASCII name) prints the reason and prompts for a new name on an interactive terminal, restarting with it; with no terminal it exits 1 with the reason (and a hint to `goga topics status` for occupied names). Ctrl-C at the prompt aborts with nothing created.

### `--publish` — create and publish in one step

`-p`/`--publish` builds the branch off an explicit base, commits only the topic's `title.txt` on it, and pushes it to `origin` — while you stay on your branch:

```bash
goga topics create Feature/Foo_Bar --publish --title "Payment retry"
# Created branch Feature/Foo_Bar and published topic 2026/feature-foo-bar
```

- The working copy, the index, and HEAD stay untouched — the commit is built through quarantined git plumbing, so a dirty tree and a detached HEAD do not interfere; the topic directory is never created on disk.
- The branch carries exactly one commit — the title file at `.goga/history/<YYYY>/<slug>/title.txt` — and is pushed to `origin` with upstream binding (`git push -u`, exactly that one branch). The topic appears on the remote board with the `new` status.
- `-t`/`--title` is **required** under `--publish` (the board reads the topic through the title file): without it, exit 1 with `--publish needs a topic title — pass --title/-t`. An explicit empty title `""` is accepted and writes the bare newline.
- Base resolution: `--base-ref` > `topics.base_ref` in `.goga/config.yml` > error. With nothing set, exit 1 with a message naming both the configuration line and the flag, including a two-line YAML example (see [Project Configuration](../configuration/project.md#topics)).
- Commit template: `--commit`/`-c` > `topics.publish_commit` > the built-in default `goga: create topic {slug}`. `{slug}` is replaced with the topic slug; a template without the placeholder is used verbatim.
- `--base-ref` or `--commit` without `--publish` is a clean error (exit 1) — they act only together with `--publish`.
- Occupancy under `--publish` adds a fourth oracle on top of the three above: any branch tree of the inventory — local and remote-tracking refs — hosting the topic directory of the slug. The conflict reads `topic '<slug>' of <YYYY> is already hosted by branch '<branch>'`, with the same re-ask/exit-1 behavior as the other oracles.
- The current branch already hosting the slug is a clean error (exit 1) — the fast path is only for fresh work; use the default `create` for the idempotent case.
- `origin` must be configured (exit 1 otherwise, before any mutation). The repository git identity must be set — `commit-tree` needs an author.
- A failed push rolls back fully: the planted branch is deleted, nothing else was ever mutated, and git's push reason surfaces as one clean error (`git failed: <git stderr>`, exit 1). A re-run with the same name then succeeds.

## `goga topics switch`

Brings the repository onto the branch hosting the requested work:

```bash
goga topics switch feat-x
# Switched to branch feat/x
```

IDENTIFIER resolves through three tiers — the first tier with a match wins, so a unique identifier never reaches a prompt:

1. exact branch name;
2. exact topic slug (local branches before remote-tracking refs);
3. prefix — a branch whose name, or whose hosted slug, starts with the input.

- Several candidates on an interactive terminal: the numbered list with each candidate's statuses is printed and a number is prompted; with no terminal, the numbered list itself is the error (exit 1).
- No candidate at all: exit 1 with a hint to run `goga topics status`.
- Already on the hosting branch: idempotent success — `Already on branch <name>` — with no working-tree probe and no mutation.
- A local host is checked out (`git switch <branch>`); a remote-only host creates the local branch from the remote-tracking ref (`git switch -c <branch> <remote>/<branch>`, reported as `Created branch <branch> from <remote>/<branch>`).
- A switch that would mutate first probes the working tree; a dirty tree exits 1 with `working tree is dirty — commit or stash before switching` before anything is touched.

The same resolution backs the switch half of `goga pipeline <name> -t <identifier>` — there, an identifier nothing hosts creates fresh work instead of failing (see [pipeline](pipeline.md#topic-switch)).

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success — the board printed, the work created, or the switch performed (including the idempotent outcomes) |
| `1` | A clean domain error: an unresolvable or ambiguous identifier, an occupied name without a terminal, a dirty working tree, a failed publication (`--publish`), a git infrastructure failure, or a broken `goga_tool_*` package failing to import during status-scale assembly |
| `2` | A usage error (unknown option, missing argument) |

## Notes

- Every mutation is local except the `--publish` push — no fetch ever happens, and `create --publish` is the only subcommand that pushes.
- `goga history status` shows the same statuses scoped to the working copy of one year (see [history](history.md)).
