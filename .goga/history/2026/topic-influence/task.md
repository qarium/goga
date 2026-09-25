# Topics Workflow: Scriptable Stdin Todo, One-Entry-Per-Topic Board, and JSON Output

Sources: `prd.md` and `adr.md` in this directory — the PRD requirements, amended by the
ADR decisions (the two are already synchronized). The task below restates the approved
scope; on any wording conflict the ADR wins.

## Current State

Two cells of the topics workflow are affected; their contracts were read during
formulation, the implementation was not.

- **`goga topics create`** (domain cell `goga/topics`): the todo of a creation comes only
  from an option value or from the interactive external editor; without a value and
  without an interactive terminal the command fails with a clean error. No stdin channel
  exists — scripted and agent-driven creation with real multi-line todo content is
  impossible.
- **`goga topics board`** (domain cell `goga/topics`, rendering in `goga/commands/topics`):
  the board shows one record per topic and hosting branch pair. Once a topic propagates
  through merges into other branches, the same topic appears several times — duplicates
  misread as distinct work, and the branches carrying the topic's history are never
  stated. The only output is a fixed-width human table (topic, branch, the todo column
  under `--info`, statuses); flags `--remote`, `--info`, `--year`. No machine-readable
  output, no host filter, no aggregated view exist.
- **Neighbors:** `goga/commands/pipeline` consumes only `ensure_topic` (untouched by this
  task); `goga/history`, `goga/topics/git`, `goga/topics/editor`, `goga/topics/hooks`
  keep their contracts — the stdin todo passes through the existing todo/creation
  amendment hooks, no new checkpoints are introduced.

## Description

Extend the topics workflow in three coordinated directions, per the PRD and ADR:

1. **Scriptable todo acquisition for `goga topics create`.** The todo option accepts an
   optional value. A value-less `--todo` means "obtain the todo": when stdin carries
   content (at least one non-whitespace character), that content becomes the todo with
   exactly the value-form semantics (verbatim text with the trailing-newline
   normalization, UTF-8, same amendment hooks); no editor opens, nothing is asked. The
   whole acquisition ladder — explicit value, else declared stdin, else the editor on an
   interactive terminal, else a clean error, including the no-source guard (stdin content
   without any declared todo source is a clean error naming `--todo`) and the skip of the
   publication ask when the todo came from stdin — is owned by the domain; the CLI layer
   only maps the value-less `--todo` into a source declaration. Stdin semantics per the
   ADR: a TTY stdin is never read; a non-TTY stdin is read fully exactly once at
   todo-resolution time (after preflight, before the editor and the ask); bytes that do
   not decode as UTF-8 are a clean error naming `--todo`; no size cap. Works on every
   creation path — default quarantined commit, `--switch`, `--publish`.
2. **One-entry-per-topic board.** The default board shows exactly one record per topic of
   the scoped year that still has an own branch — a hosting branch whose normalized slug
   equals the topic slug; a remote-tracking ref qualifies, so remote-only topics stay
   visible. A topic without an own branch (history only in merged hosts) produces no
   default record. Colliding own branches resolve deterministically: the current branch
   when among them, then a local branch over a remote-tracking one, then the display-name
   alphabet. The record carries a hosts field — every branch carrying the topic's
   history, the own branch included, alphabetical, a local branch and its remote twin
   collapsed under the local name — and the statuses of the own branch only. The table
   gains a hosts column (order: topic, branch, hosts, todo, statuses; entries wrap like
   statuses). A repeatable `--host` option filters by exact display name with union
   semantics; an unknown name yields the empty-board behavior, never an error; under
   `--per-host` the filter keeps the rows of the named hosts only. The
   per-host record collection stays the single source of facts: the aggregate view is a
   projection of it, so both views derive from one read pass and cannot drift.
3. **Expanded per-host view and JSON output.** `--per-host` keeps the previous row model
   as the complete audit view — one record per topic and hosting branch, including topics
   without an own branch — in the table and in JSON. `--json` prints the board as a
   pretty-printed JSON array through the project's `beautiful_json` practice; default
   records carry exactly the stable fields `topic`, `branch`, `hosts`, `statuses`,
   `current`, `remote`, `todo` (`todo` a string or `null`); per-host records carry the
   same without `hosts`; an empty board prints `[]`; `--info` with `--json` is a clean
   error; `--remote` and `--year` apply to JSON exactly as to the table. The field names
   and record shapes are a stable consumer contract; the key order is not.

## Scope

**In scope:**

- The extended todo acquisition of `goga topics create`: the value-less `--todo` reading
  stdin, the no-source guard, precedence (value over stdin) and emptiness rules, the
  publication-ask skip — across all three creation paths.
- The one-record-per-topic board: the own-branch visibility rule, the multiple-own-branch
  tie-break, the hosts field, own-branch statuses, the current marker, the hosts table
  column, the repeatable `--host` filter.
- The `--per-host` expanded audit view in table and JSON.
- The `--json` output with the stable record schema.
- Synchronization of the CODEMANIFEST declarations and `.usages` documents of the two
  affected cells with the new behavior.
- Update of the project-level `click` practice with the optional-value option pattern
  (approved during formulation).

**Out of scope:**

- A stdin channel for `goga topics switch --todo` — it stays editor-only (explicitly
  confirmed by the owner during formulation).
- Changes to delete, ensure, or publication semantics beyond the ask-skip rule.
- Changes to editor behavior (`$VISUAL`/`$EDITOR`/`vi`, cancel semantics).
- Changes to the status scale or history-tree semantics.
- Network operations: the board reads refs as today and never fetches.
- Per-host statuses inside the default aggregate view and any cross-branch status
  aggregation into the single record (both explicitly rejected).
- New subcommands and JSON schema versioning or negotiation machinery.

## Acceptance Criteria

1. In a non-interactive environment, piping multi-line content with a value-less
   `--todo` creates the topic whose `todo.md` contains exactly the piped content; no
   editor or prompt appears; one result line prints; exit code 0.
2. Piping non-empty content without declaring any todo source fails with a clean error
   naming `--todo` — the content is never silently ignored.
3. An explicit todo value wins over piped stdin; an empty or content-free stdin keeps
   today's flows: editor on a terminal, clean error headless where the todo is required,
   and a successful todo-less `create --switch` headless.
4. When the todo came from stdin, no publication ask appears; `--publish` still publishes
   with full rollback on failure.
5. A topic carried by its own branch plus at least one merged host appears exactly once:
   branch shows the own branch, hosts lists all carrying branches including the own one
   (alphabetical), and no duplicate rows remain; a topic whose history survives only in
   merged hosts appears in no default record (table and JSON) but keeps its rows under
   `--per-host`.
6. The single record's statuses are the own branch's maximal statuses; `--per-host` shows
   one row per carrying branch with that branch's own statuses.
7. `goga topics board --json` prints a parseable pretty-printed JSON array whose records
   carry exactly the stable keys; `todo` is a string or `null`; an empty board prints
   `[]`; `--json --info` is a clean error; `--per-host --json` records carry the per-host
   shape.
8. Existing interactive behaviors — editor entry, value-form todo, switch, delete —
   behave exactly as before.
9. Board invocations (table, per-host, JSON) leave the working copy and the repository
   untouched.
10. `--host one --host two` filters by exact display name with union semantics: the
    default view keeps the records whose hosts list contains any of the given names
    (an own branch still required — the filter never resurrects a hidden topic);
    `--per-host` keeps the rows of the named hosts only; an unknown host name leaves
    an empty board — or `[]` under `--json` — with exit 0.
11. When several distinct branches normalize into one topic slug, the default record
    shows exactly one own branch — the current branch when it is among them, otherwise
    a local branch over a remote-tracking one, otherwise the first in display-name
    alphabet; `--per-host` still shows every colliding row.
12. Piping bytes that do not decode as UTF-8 with a value-less `--todo` fails with a
    clean error naming `--todo` — no topic, branch, or file is created.
13. In a non-interactive environment, piping multi-line content with a value-less
    `--todo` and `--switch` creates and checks out the topic whose working-copy
    `todo.md` contains the piped content, uncommitted; no editor or prompt appears.

## Stack

- **Frameworks:** click ≥ 8.0 (CLI surface — optional-value option, repeatable option,
  flags, echo, clean errors).
- **Libraries:** Python standard library only for the new behavior — `json` (through the
  `beautiful_json` practice), `sys` (stdin reading and TTY detection). pytest ≥ 8.0,
  pytest-cov, ruff for tests and linting (existing project toolchain).
- **Infrastructure:** none — no databases, brokers, or new services; no new third-party
  dependencies in `pyproject.toml`.

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| click | `.goga/usages/cooks/click.md` | updated — add the optional-value option pattern (a value-less form distinguishable from an absent option) |
| beautiful_json | `.goga/usages/cooks/beautiful_json.md` | existing — covers the JSON output fully |
| editor | `.goga/usages/cooks/editor.md` | existing — the editor protocol is unchanged |
| conventions | `.goga/usages/conventions.md` | existing — base project practice |

No new external dependencies; the stdin channel is pure standard library and needs no
practice file.

## Risks and Constraints

- **No regression of interactive flows** — editor-based creation, value-form todo entry,
  switch, and delete stay byte-identical; the stdin channel never replaces the editor
  session (constraint: the editor requires an interactive terminal).
- **Clean-error discipline** — every new failure mode (undeclared stdin content, invalid
  UTF-8, `--json --info`) is one actionable message on stderr, exit 1, no traceback.
- **The board is strictly read-only** — no checkout, no worktree, no mutation in any
  view or output mode.
- **JSON schema stability** — the published field names and record shapes are a stable
  contract; later changes must be additive and non-breaking.
- **One-read stdin hazard** — a stream cannot be re-read; the guard and the resolution
  must share a single full read, and a TTY must never be read (a blocking read would hang
  every interactive create). This is the main correctness risk of direction 1.
- **View drift hazard** — the aggregate and per-host views must derive from one
  collection pass; a second git read or a separate aggregation path invites semantic
  drift (main risk of direction 2).
- **Optional-value option mapping** — the CLI must distinguish three states (value
  given, declared without value, absent); the mapping pattern lands in the `click`
  practice.
- **Contract documentation ships with the change** — the CODEMANIFEST declarations and
  `.usages` documents of both cells describe the new behavior when it changes.

## Scope Estimate

Single task (approved by the owner during formulation). Rationale: the board directions
(one-entry-per-topic, `--per-host`, `--host`, `--json`) are facets of one reworking of
the board collection and would produce inconsistent intermediate states if split; the
stdin direction, though separable, is small against the board work and shares the same
two cells and the same contract-sync pass. Downstream decomposition onto cells and
execution steps happens in the brainstorm and planning stages.

## Existing Architecture

- **`goga/topics`** — the topics domain: owns the todo acquisition ladder (new stdin
  source, no-source guard, ask-skip) and the board collection (per-host records stay the
  source of facts; the aggregated default view is computed from them). Imports from
  `goga/history`, `goga/topics/git`, `goga/topics/editor`, `goga/topics/hooks` — none of
  those contracts change.
- **`goga/commands/topics`** — the CLI surface: maps the value-less `--todo` into a
  source declaration; adds the `--host`, `--per-host`, and `--json` flags; renders the
  hosts column and the JSON output; keeps `--info` table semantics. No computation moves
  into this cell.
- **Consumers:** `goga/commands` registers the group (group surface unchanged);
  `goga/commands/pipeline` imports only `ensure_topic` — unaffected.
- **Integration requirement:** both affected cells ship updated CODEMANIFEST declarations
  and `.usages` documents together with the behavior.

## Notes

- Decisions settled during the formulation interview: the task statement was approved as
  proposed (with the explicit confirmation that `switch` keeps its editor-only todo);
  the stack was approved with the `click.md` practice update; the single-task scope was
  approved.
- The ADR supersedes the PRD where the two differ — the PRD was already patched during
  discovery, so the two documents agree; on any residual conflict the ADR wins.
- Key ADR terms for the implementer: host, own branch (including the remote-tracking
  form), status, hosts field, value-less `--todo`, stdin content, content-free stdin,
  no-source guard.
