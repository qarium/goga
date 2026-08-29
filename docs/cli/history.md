# goga history

Work with the `.goga/history/` tree — its per-year topics, their statuses, and their paths.

`goga history` is a Click group with four subcommands (`list`, `status`, `path`, `ensure`) over the history domain. Everything is host-side and read-only except `ensure`; domain errors surface as clean one-line errors (exit 1, no traceback).

## Synopsis

```bash
goga history list
goga history status [YEAR] [-t TOPIC] [-s STATUS]...
goga history path [TOPIC] [-f FILENAME] [-y YEAR]
goga history ensure [NAME]
```

## `goga history list`

The inventory view: one `YYYY/` line per year, each topic indented under its year.

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
feat-x [defined] [planned]
release-1-3-0 [done] [mkdocs.published]
```

A topic carries its **maximal present statuses** in scale order — one bracketed segment per status:

| Status | Artifact | |
|---|---|---|
| `empty` | — | no artifact yet |
| `defined` | `prd.md` | |
| `discovered` | `adr.md` | |
| `backlog` | `task.md` | |
| `designed` | `arch.md` | |
| `specified` | `design.md` | |
| `planned` | `plan.md` | |
| `done` | `completed/plan.md` | |

A topic can carry several statuses at once: every artifact present that is outranked by no other present artifact stays visible (tool statuses included, shown qualified such as `mkdocs.published` — see [Tools](../tools.md) for how a tool package registers its own statuses). YEAR defaults to the current year and is never printed; topics come out alphabetically.

The status segments print colored (`cyan`) unless `NO_COLOR` is set in the environment.

### Filters

- `-t`/`--topic` keeps the topics whose normalized slug contains the normalized filter as a substring.
- `-s`/`--status` is repeatable and keeps the topics carrying **at least one** of the requested statuses — any-of matching. Both built-in names (`-s planned`) and qualified tool names (`-s mkdocs.published`) are valid; an unknown name is a clean error before anything prints.
- Both filters combine by AND. An empty result prints nothing and exits 0 — it is not an error.

```bash
goga history status                 # the current year, every topic
goga history status 2025            # one explicit year
goga history status -s planned      # every topic carrying [planned]
goga history status -t release      # every topic whose slug contains "release"
```

## `goga history path`

Prints exactly one path of the history tree — and nothing else — for scripting:

```bash
plan=$(goga history path -f plan.md)
```

TOPIC defaults to the current git branch (taken raw, as a branch name or a slug — the two compose identically through the slug grammar). With `-f`/`--file` the artifact file path prints (the filename is taken verbatim and must carry an extension); otherwise the topic directory. `-y`/`--year` selects the year (default: the current one). Nothing is created on disk.

## `goga history ensure`

Creates the topic directory of the current year, idempotently: parents are created as needed and an existing directory is a success, not a conflict. NAME defaults to the current git branch. Prints nothing on stdout — the exit code carries the result. Only directories: no artifact file is created, and occupancy is not reported.

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success — the tree, statuses, or path printed, or the directory ensured |
| `1` | A clean domain error: an unknown `-s` status name, an empty topic filter or slug, an undeterminable current branch where a topic default is needed, or a broken `goga_tool_*` package failing to import during status-scale assembly |
| `2` | A usage error (unknown option, too many arguments) |

## Notes

- The topic slug grammar: lowercase, non-ASCII dropped, anything outside `[a-z0-9]` becomes `-`, repeat hyphens collapsed, edge hyphens trimmed (`Feature/Foo_Bar` → `feature-foo-bar`, `release/1.3.0` → `release-1-3-0`).
- `goga topics status` shows the same statuses across branches; `goga history status` shows the working copy of one year (see [topics](topics.md)).
