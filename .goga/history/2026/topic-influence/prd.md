# Topics Workflow: Stdin Todo Creation, One-Entry-Per-Topic Board, and JSON Output

## Problem

The `goga` CLI topics workflow has three validated problems:

1. **Topic creation is not scriptable with real content.** Automation contexts — CI jobs, git hooks, agent pipelines — need to create topics with multi-line todo content and no interactive terminal. Today the todo of `goga topics create` can only be given as an option value (impractical for multi-line text because of shell quoting) or through the external editor (which requires an interactive terminal; without one the command fails with a clean error). Scripted creation of topics with meaningful todos is therefore impossible without workarounds.

2. **The board duplicates merged topics and hides propagation.** The board shows one row per topic-branch pair: once a topic propagates through merges into other branches (for example `main` or release branches), the same topic appears several times. The list is noisier than the actual amount of work, a repeated topic can be mistaken for distinct work (leading to duplicated effort or wrong status reading), and which branches actually carry the topic's history is never shown explicitly — propagation is implied by duplicates rather than stated.

3. **The board has no machine-readable output.** External tools and agents need to consume the board inventory programmatically, but the only output is a fixed-width table intended for humans; parsing it is fragile, and no stable structured representation of the board exists.

## Users

One primary user — the goga repository developer who manages work as topics — acting in three modes:

- **Scripted caller.** Invokes `goga topics create` from CI, hooks, or agent pipelines. No interactive terminal is available; the content is multi-line; behavior must be deterministic, with clean, actionable errors.
- **Board reader.** Runs `goga topics board` to see all work of the repository at a glance. Wants exactly one entry per topic, explicit visibility of the branches carrying the topic, and statuses that reflect the topic's own branch.
- **Tool builder.** Builds external tools and agents (dashboards, LLM agents, scripts) that consume the board. Needs a stable field schema that does not change under them.

Secondary actor: the machine consumers themselves (external tools, agent pipelines) — they cannot parse human tables and depend on schema stability.

All existing interactive users keep their current editor-based flows unchanged.

## Goals

1. Scripted and agent-driven callers can create topics with complete multi-line todo content in non-interactive environments, as reliably as interactive users can today.
2. A board reader sees exactly one entry per topic, with the branches carrying the topic's history shown explicitly, so the inventory reflects the real volume of work and cannot be misread as duplicated work.
3. External tools and agents consume the same board inventory through a stable structured representation, without parsing human-oriented formatting.

## User Experience

### Creating a topic with the todo from stdin

The caller pipes the todo content and declares the intent with a value-less `--todo`:

```text
printf 'First line\nSecond line\n' | goga topics create Feature/Foo --todo --from-current
```

- The declared value-less `--todo` means "obtain the todo": when stdin actually carries content that is not empty or whitespace-only, that content becomes the todo — with exactly the same semantics as an option value (text as entered plus a trailing newline, UTF-8, subject to the same amendment hooks). No editor opens, nothing is asked.
- When the value-less `--todo` finds no usable stdin content, the product behaves as today: the external editor opens on an interactive terminal; without a terminal the command fails with a clean error naming the option.
- An explicit `--todo "text"` value always wins over stdin content; an empty value still counts as absent, as today.
- Supplying stdin content without declaring any todo source (neither a value nor a value-less `--todo`) is a clean error that names `--todo` — piped content is never silently ignored.
- An empty, whitespace-only, or content-free stdin means "no todo given": on the interactive terminal the editor opens; headless, the todo is simply absent where it is optional (the `--switch` path without a todo keeps working headless) and a clean error names the option where the todo is required (the default path).
- When the todo came from stdin, the interactive publication ask ("Publish the branch to origin?") never appears: the command takes the local path, and publication happens only under `--publish` (with its existing behavior and rollback).
- The stdin channel works on every creation path — the default quarantined-commit path, `--switch`, and `--publish`.
- Successful creation prints one result line on stdout and exits 0, as today.

### Reading the board: one entry per topic

`goga topics board` shows exactly one record per topic of the scoped year that still has its own branch:

- The **branch** column shows the topic's own branch — the hosting branch whose normalized slug equals the topic slug; a remote-tracking ref may be the own branch, so remote-only topics keep their record. A topic without an own branch — one whose history survives only in merged-work hosts — produces no default record: only history remains of it. When several hosting branches normalize to the topic slug, the shown own branch is chosen deterministically: the current branch when it is among them; otherwise a local branch over a remote-tracking one; ties broken alphabetically.
- The **hosts** column lists every branch carrying the topic's history, the own branch included, ordered alphabetically by display name. A local branch and its remote twin count as one host under the local name; remote mode lists remote-tracking names. Entries wrap onto continuation lines like statuses do.
- The **statuses** of the single record are the maximal statuses of the topic's own branch only — artifacts that exist solely on merged hosts do not advance them.
- The current-row marker (`*`) marks the record whose topic the current working branch hosts.
- A repeatable **--host NAME** option filters the board by hosting branch (exact display name): the default view keeps the records whose hosts list contains any of the given names (an own branch is still required — the filter never resurrects a hidden topic); the per-host view keeps the rows of the named hosts. Several values unite (any-of); an unknown name yields the empty-board behavior, never an error.
- The todo summary (first qualifying line of `todo.md` after `#` markers are stripped), the record ordering, the strictly read-only behavior, and the empty-board behavior (prints nothing, exits 0) are unchanged.

### Auditing per branch: the expanded view

`goga topics board --per-host` switches to the expanded audit view: one record per topic and hosting branch pair, showing that branch's own statuses — the previous row model, complete including topics that no longer have an own branch (their merged-host rows stay visible here and only here). The view is available in the table and in JSON. Per-host records keep the established semantics: the current marker applies per hosting branch, the remote marker per ref, and a local branch still absorbs its remote twin.

### Consuming the board as JSON

`goga topics board --json` prints the board as a pretty-printed JSON array on stdout:

- Default records carry exactly the stable fields `topic`, `branch`, `hosts`, `statuses`, `current`, `remote`, `todo`; `todo` is a string or `null`.
- Per-host records (under `--per-host --json`) carry `topic`, `branch`, `statuses`, `current`, `remote`, `todo` — no `hosts`.
- An empty board prints `[]` and exits 0.
- `--remote` and `--year` apply to JSON exactly as to the table.
- `--info` combined with `--json` is a clean error: the todo is always present in JSON.

### Failure behavior

Every failure remains a clean CLI error: one actionable message on stderr, exit code 1, no traceback. Failed states leave the repository as it was — the board is read-only, and a failed creation or publication follows the existing rollback behavior.

## Requirements

### R1. Topic creation with the todo from stdin (`goga topics create`)

1. The todo option must accept an optional value. With a value it is the todo, unchanged; an empty value counts as an absent option, unchanged.
2. A value-less `--todo` must resolve the todo from stdin when stdin carries content that is neither empty nor whitespace-only.
3. Stdin-supplied todo content must be treated exactly like value-supplied content: written as entered plus a trailing newline, UTF-8, and passed through the same todo amendment hooks.
4. When the value-less `--todo` yields no usable stdin content, the product must behave as today: the external editor opens on an interactive terminal; without one, a clean error names the option.
5. An explicit todo value must take precedence over stdin content.
6. When stdin carries non-empty, non-whitespace content and no todo source is declared, the command must fail with a clean error that names `--todo`; supplied stdin content must never be silently ignored.
7. An empty, whitespace-only, or content-free stdin counts as "no todo given": the editor opens on an interactive terminal; headless, the todo is absent where it is optional (the `--switch` path without a todo must keep succeeding headless) and a clean error names the option where the todo is required (the default path).
8. When the todo was resolved from stdin, the interactive publication ask must not appear; publication happens only under `--publish`, with its existing semantics including full rollback on failure.
9. All other creation behavior is preserved: preflight before any input, base resolution, the default quarantined commit path, `--switch`, `--publish`, one result line on stdout, exit 0 on success.

### R2. Board: one record per topic (`goga topics board`)

1. The default board must show exactly one record per topic of the scoped year that has an own branch; a topic hosted by several branches must not produce duplicate records, and a topic without an own branch must produce no default record.
2. The branch field must show the topic's own branch — the hosting branch whose normalized slug equals the topic slug; a remote-tracking ref qualifies, so remote-only topics keep their record.
3. When no own branch exists — the topic's history survives only in merged-work hosts — the default board must not show the topic (its rows stay in the per-host audit view); when several hosting branches normalize to the topic slug, the shown own branch must be chosen deterministically: the current branch when it is among them, otherwise a local branch over a remote-tracking one, ties broken alphabetically.
4. A hosts field must list every branch carrying the topic's history, the own branch included, ordered alphabetically by display name. A local branch and its remote twin are one host under the local name; remote mode lists remote-tracking display names.
5. The statuses field must show the maximal statuses of the own branch only — never statuses that exist solely on other carrying branches.
6. The current marker must apply when the current working branch hosts the topic.
7. The table gains a hosts column whose entries wrap like statuses; the existing columns, the `--info` todo column, the todo summary rule, the record ordering, the read-only guarantee, and the empty-board behavior are unchanged. The default column order is topic, branch, hosts, todo, statuses.
8. A repeatable `--host` option must filter the board by exact hosting-branch display name: the default view keeps the records whose hosts list contains any of the given names (an own branch still required); the per-host view keeps the rows of the named hosts. Several values unite (any-of, duplicates collapse); an unknown name yields the empty-board behavior (nothing printed, or `[]` under `--json`; exit 0), never an error.

### R3. Board: expanded per-host view

1. `--per-host` must switch the board to one record per topic and hosting branch, showing that hosting branch's own statuses — the previous row model, complete including topics without an own branch — in the table and in JSON.
2. Per-host records keep the established semantics: the current marker per hosting branch, the remote marker per ref, and the local-over-remote-twin collapse.

### R4. Board: JSON output

1. `--json` must print the board as a pretty-printed JSON array on stdout, serialized through the project's `beautiful_json` practice (`indent=4`, `sort_keys=True`, `ensure_ascii=False`, one trailing newline); an empty board prints `[]`; the command exits 0. The stable contract is the field names and record shapes, not the key order.
2. Default records must carry exactly the fields `topic`, `branch`, `hosts`, `statuses`, `current`, `remote`, `todo`, with `todo` a string or `null`.
3. Per-host records under `--per-host --json` must carry `topic`, `branch`, `statuses`, `current`, `remote`, `todo` without `hosts`.
4. `--info` combined with `--json` must fail with a clean error (the todo is always present in JSON).
5. `--remote` and `--year` must apply to the JSON output exactly as to the table.
6. The JSON field names and record shapes are a stable contract: future changes must not break consumers.

### R5. Cross-cutting

1. Interactive editor flows and value-form todo entry must not regress.
2. Every failure is a clean CLI error: one actionable message on stderr, exit code 1, no traceback; successes exit 0 (an empty board included).
3. The board remains strictly read-only: no checkout, no worktree, no mutation of the working copy or the repository.

## Constraints

1. **No regression of interactive flows.** Existing editor-based creation, value-form todo entry, switch, and delete behavior stays as is.
2. **Clean-error discipline.** All new failure modes follow the CLI convention: actionable message on stderr, exit 1, no traceback.
3. **Board is read-only.** The aggregated board, the per-host view, and the JSON output must not check out, create worktrees, or mutate anything.
4. **JSON schema stability.** The published field names and record shapes are a stable contract for external consumers; changes after release must be additive and non-breaking.
5. **Contract documentation ships with the change.** The CODEMANIFEST declarations and `.usages` documents of the affected cells (the topics domain and the topics command group) must describe the new behavior when it changes.
6. **Editor requires an interactive terminal.** Stdin supplies content non-interactively; it never replaces the interactive editor session.

## Scope

### In Scope

- The extended todo acquisition of `goga topics create` (value-less `--todo` reading stdin, the no-source guard, precedence and emptiness rules, publication-ask skip) across all three creation paths.
- The one-record-per-topic board: the own-branch visibility rule (no own branch — no default record), the multiple-own-branch tie-break, the hosts field including the own branch, own-branch statuses, current marker, the hosts table column, and the repeatable `--host` filter.
- The `--per-host` expanded view in table and JSON.
- The `--json` output with the stable record schema.
- Synchronization of the affected cells' CODEMANIFEST declarations and `.usages` documents with the new behavior.

### Out of Scope

- A stdin channel for `goga topics switch --todo` (it stays editor-only).
- Changes to delete, ensure, or publication semantics beyond the ask-skip rule.
- Changes to editor behavior (`$VISUAL`/`$EDITOR`/`vi`, cancel semantics).
- Changes to the status scale or history-tree semantics.
- Network operations: the board reads refs as today and never fetches.
- Per-host statuses inside the default aggregate view, and any cross-branch status aggregation into the single record (both explicitly rejected).
- New subcommands (for example a topic-detail command) and JSON schema versioning or negotiation machinery.

## Success Criteria

1. In a non-interactive environment, piping multi-line content with a value-less `--todo` creates the topic whose `todo.md` contains exactly the piped content; no editor or prompt appears; one result line prints; exit code is 0.
2. Piping non-empty content without declaring any todo source fails with a clean error naming `--todo` — the content is never silently ignored.
3. An explicit todo value wins over piped stdin; an empty or content-free stdin keeps today's flows: editor on a terminal, clean error headless where the todo is required, and a successful todo-less `create --switch` headless.
4. When the todo came from stdin, no publication ask appears; `--publish` still publishes with full rollback on failure.
5. A topic carried by its own branch plus at least one merged host appears exactly once: branch shows the own branch, hosts lists all carrying branches including the own one (alphabetical), and no duplicate rows remain; a topic whose history survives only in merged hosts appears in no default record (table and JSON) but keeps its rows under `--per-host`.
6. The single record's statuses are the own branch's maximal statuses; `--per-host` shows one row per carrying branch with that branch's own statuses.
7. `goga topics board --json` prints a parseable pretty-printed JSON array whose records carry exactly the stable keys; `todo` is a string or `null`; an empty board prints `[]`; `--json --info` is a clean error; `--per-host --json` records carry the per-host shape.
8. Existing interactive behaviors — editor entry, value-form todo, switch, delete — behave exactly as before.
9. Board invocations (table, per-host, JSON) leave the working copy and the repository untouched.
10. `--host one --host two` filters the board to the topics those hosts carry (union, exact display-name match; an own branch still required in the default view); an unknown host name leaves an empty board — or `[]` under `--json` — with exit 0.
