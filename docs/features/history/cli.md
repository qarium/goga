# goga history

Work with the `.goga/history/` tree — its per-year topics, their statuses, and their paths.

`goga history` is a Click group with five subcommands (`list`, `status`, `path`, `ensure`, `prune`) over the history domain. Everything is host-side; all of it is read-only except `ensure` (creates a directory) and `prune` (deletes topic directories). Domain errors surface as clean one-line errors (exit 1, no traceback).

## Synopsis

```bash
goga history [-y YEAR] list|status [-t TOPIC] [-s STATUS]|path [TOPIC] [-f FILENAME]|ensure [NAME]|prune [--dry-run]
```

## Year addressing

The year is addressed by the group option `-y`/`--year` alone — given once, *before* the subcommand — and every subcommand reads the same value. The subcommands carry no year surfaces of their own: the removed forms are usage errors (exit 2) — a positional `YEAR` (`goga history status 2025`, `goga history prune 2025`) or a year option placed after the subcommand (`goga history path feat-x -y 2025`).

- Without `-y`, `list` prints every year; `status`, `path`, `ensure`, and `prune` take the current year.
- An empty value (`-y ""`) counts as not set.
- The CLI does not validate the value — the domain owns the year semantics; a year missing from the tree is an empty result, not an error.

```bash
goga history -y 2025 status
goga history -y 2025 path release/1.3.0 -f plan.md
goga history -y 2025 prune
```

## `goga history list`

The inventory view: one `YYYY/` line per year, each topic indented under its year. With `-y`/`--year` the tree narrows to that year's section alone.

```
2025/
 └── release-1-3-0
2026/
 └── feat-x
 └── history-commands
```

An empty tree prints nothing. Read-only — statuses and artifact names never appear.

## `goga history status`

Prints the topics of one year, one `topic [status] [status] …` line each:

```
feat-x [planned]
release-1-3-0 [done] [mkdocs.published]
```

A topic carries its **maximal present statuses** in scale order — one bracketed segment per status:

| Status | Artifact | Notes |
|---|---|---|
| `empty` | — | no artifact yet |
| `todo` | `todo.md` | written by the `--todo` editor entries (`goga topics create/switch --todo`, `goga pipeline … --todo`) |
| `defined` | `prd.md` | |
| `discovered` | `adr.md` | |
| `backlog` | `task.md` | |
| `designed` | `arch.md` | |
| `specified` | `design.md` | |
| `planned` | `plan.md` | |
| `done` | `completed/plan.md` | |

A topic can carry several statuses at once: every artifact present that is outranked by no other present artifact stays visible (tool statuses included, shown qualified such as `mkdocs.published` — see [Tools](../tools/index.md) for how a tool package registers its own statuses). The year comes from the group's `-y`/`--year` (default: the current year) and is never printed; topics come out alphabetically.

The status segments print colored (`cyan`) unless a non-empty `NO_COLOR` is set in the environment.

### Filters

- `-t`/`--topic` keeps the topics whose normalized slug contains the normalized filter as a substring.
- `-s`/`--status` is repeatable and keeps the topics carrying **at least one** of the requested statuses — any-of matching. Both built-in names (`-s planned`) and qualified tool names (`-s mkdocs.published`) are valid; an unknown name is a clean error before anything prints.
- Both filters combine by AND. An empty result prints nothing and exits 0 — it is not an error.

```bash
goga history status                 # the current year, every topic
goga history -y 2025 status         # one explicit year
goga history status -s planned      # every topic carrying [planned]
goga history status -t release      # every topic whose slug contains "release"
```

## `goga history path`

Prints exactly one path of the history tree — and nothing else — for scripting:

```bash
plan=$(goga history path -f plan.md)                        # the current year
plan=$(goga history -y 2025 path release/1.3.0 -f plan.md)  # one explicit year
```

TOPIC defaults to the current git branch (taken raw, as a branch name or a slug — the two compose identically through the slug grammar). With `-f`/`--file` the artifact file path prints (the filename is taken verbatim and must carry an extension); otherwise the topic directory. The year comes from the group's `-y`/`--year` (default: the current one). Nothing is created on disk.

## `goga history ensure`

Creates the topic directory of the scoped year, idempotently: parents are created as needed and an existing directory is a success, not a conflict. The year comes from the group's `-y`/`--year` (default: the current one). NAME defaults to the current git branch. Prints nothing on stdout — the exit code carries the result. Only directories: no artifact file is created, and occupancy is not reported.

## `goga history prune`

Deletes the orphan topics of one year — the topics no branch of the repository inventory hosts — and prints one slug per line; an empty result prints nothing and exits 0. The year comes from the group's `-y`/`--year` (default: the current year) — only that year is touched.

```bash
goga history prune --dry-run        # the current year: list the candidates, delete nothing
goga history -y 2025 prune --dry-run
goga history -y 2025 prune          # one explicit year
```

- A topic is protected when any local branch name, or the short name of any remote-tracking ref (the part after the first `/`), normalizes to the topic slug — in every year, not just the scoped one. A branch carrying the topic as merged work does not protect it.
- Deletion is unconditional — no status protects a topic, a `done` orphan goes too — and irreversible: the history tree is not in git, so a deleted topic directory cannot be recovered. Run with `--dry-run` first.
- Filesystem-only: no branch, ref, or index of git is touched — the only git call is the read-only ref listing.

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success — the tree, statuses, or path printed, the directory ensured, or the orphans pruned (possibly none) |
| `1` | A clean domain error: an unknown `-s` status name, an empty topic filter or slug, an undeterminable current branch where a topic default is needed, a broken `goga_tool_*` package failing to import during status-scale assembly, or a prune failure (a git failure of the ref listing, a missing git binary, a topic directory that cannot be deleted, or a directory name that normalizes to an empty slug) |
| `2` | A usage error (unknown option, too many arguments — including the removed year forms (a positional YEAR, a year option after the subcommand)) |

## Notes

- The topic slug grammar: lowercase, non-ASCII dropped, anything outside `[a-z0-9]` becomes `-`, repeat hyphens collapsed, edge hyphens trimmed (`Feature/Foo_Bar` → `feature-foo-bar`, `release/1.3.0` → `release-1-3-0`).
- `goga topics board` shows the same statuses across branches; `goga history status` shows the working copy of one year (see [topics](../topics/cli.md)).
