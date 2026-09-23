# Plan: `topic-influence`

Result of compiling `.goga/history/2026/topic-influence/design.md` (the
design-review-corrected architectural decision) into ralphex-executable
tasks. The two changed CODEMANIFESTs (`goga/topics`,
`goga/commands/topics`) are already materialized by the apply stage and are
**read-only** for every task below.

---

## Purpose

Implement the topic-influence feature over the existing topics domain and
its CLI:

- the board becomes **two projections** of one collection pass — the
  per-host audit records (`collect_topic_board`, unchanged shape plus the
  `hosts` record filter) as the single source of facts, and the new
  aggregated default view (`aggregate_topic_board` → `BoardEntry`) with
  exactly one entry per topic that still has its own branch;
- the CLI `goga topics board` gains `--host` (repeatable),
  `--per-host` (the audit table), and `--json` (the machine-readable
  projection via the `beautiful_json` practice), with `--json --info` as a
  clean error;
- the creation gains the **todo acquisition ladder** — explicit value →
  declared stdin (`--todo` without a value, an optional-value click option
  with a reserved sentinel) → editor → clean path rules — with the
  publication ask skipping itself when the todo came from stdin.

The most important contract–code gaps: `BoardEntry`,
`aggregate_topic_board`, `render_topic_host_rows`, `render_board_json` do
not exist; `collect_topic_board`, `create_topic`, `topics.board`,
`topics.create`, `render_topic_board` lack the new parameters; both facades
lack the new exports; `_resolve_todo`/`_publication_asked` implement the old
todo policy; the `create` help docstring still documents the abolished
value-less-`--todo` usage error.

Strategy: implement in the design's dependency order — the domain leaf
`goga/topics/board.py` first, then the `goga/topics` facade, then
`goga/topics/creation.py`; the consumer cell `goga/commands/topics` after
the whole domain package (renderers → board surface → create surface →
facade); one integration-test task per package at the end. Every coding
task follows the TDD workflow (contract tests → code → interface
verification → logic tests → debugging → contract re-verification → lint).

## Context

### Contract Surface

#### Cell `goga/topics` (manifest: `goga/topics/CODEMANIFEST`)

**Entity: `BoardEntry`** — NEW
- Type: `class` (data entity)
- Declared `location`: `board.py`
- Facade obligation: importable from `goga.topics` (after Task 2), listed in `__all__`
- Constructor: `BoardEntry(topic: str, branch: str, hosts: list[str], statuses: list[str], current: bool, remote: bool, todo: str | None = None)`
- Properties: `topic -> str` (the topic slug — the directory name of the
  topic); `branch -> str` (the display name of the topic's own branch — the
  hosting branch whose branch part (the whole name of a local branch, the
  short name of a remote-tracking ref) normalizes into the topic slug);
  `hosts -> list[str]` (display names of every branch carrying the topic's
  history, own branch included, alphabetical by display name);
  `statuses -> list[str]` (maximal present status names on the own branch,
  in scale order); `current -> bool` (True when the current working branch
  hosts the topic); `remote -> bool` (True when the own branch is a
  remote-tracking ref); `todo -> str | None` (the todo summary read from
  the own branch; `""` for a todo.md whose every line reduces to
  emptiness — presence differs from absence)
- Semantic requirements: one entry of the default board — one topic that
  still has its own branch, with every branch carrying its history. A pure
  frozen `kw_only` dataclass per the `convention` practice, mirroring
  `BoardRecord`.
- Imported dependencies: none beyond the module's existing imports.
- Annotation context: `convention` for the data-model rules and
  intra-package imports.

**Routine: `aggregate_topic_board`** — NEW
- Type: `function`
- Declared `location`: `board.py`
- Facade obligation: importable from `goga.topics` (after Task 2), listed in `__all__`
- Signature: `aggregate_topic_board(records: list[BoardRecord], hosts: tuple[str, ...] | None = None) -> entries: list[BoardEntry]`
- Semantic requirements: project the per-host records into the default
  board — exactly one entry per topic that still has an own branch;
  read-only over `records` (no mutation, no re-sort, no git access — every
  fact comes from the records); the own-branch requirement precedes the
  `hosts` filter (the filter never resurrects a topic without an own
  branch); an empty `records` yields the empty list; an unknown `hosts`
  name yields the empty list, never an error. The full algorithm is in
  Task 1.
- Imported dependencies: `normalize_topic_slug` and
  `assemble_status_scale` from `goga/history` (both already imported in
  `board.py`).
- Annotation context: `topic-paths` for the slug normalization pattern.

**Routine: `collect_topic_board`** — CHANGED
- Type: `function`
- Declared `location`: `board.py`
- Facade obligation: already importable from `goga.topics` (unchanged)
- Signature: `collect_topic_board(year: str | None = None, remote: bool = False, hosts: tuple[str, ...] | None = None) -> records: list[BoardRecord]`
- Change: gains the `hosts` record filter — exact display-name equality,
  union across values; `None` or empty keeps every record; an unknown name
  yields the empty list, never an error; the filter composes with `remote`
  mode (display names are then remote-tracking names). Steps 1–8 of the
  declared algorithm are unchanged; the filter is step 9, the sort step 10.
- Annotation context: `topic-paths`, `topic-statuses`,
  `refs-and-switching` (unchanged usage).

**Routine: `create_topic`** — CHANGED
- Type: `function`
- Declared `location`: `creation.py`
- Facade obligation: already importable from `goga.topics` (unchanged)
- Signature: `create_topic(branch_name: str, base_ref: str, todo: str | None = None, todo_from_stdin: bool = False, publish: bool = False, commit_message: str | None = None, year: str | None = None, switch: bool = False) -> result: str`
- Change: `todo_from_stdin` slots in directly after `todo`; the todo
  resolves through the **acquisition ladder** (value → declared stdin →
  editor → path rules); the publication ask skips itself when the todo came
  from stdin. The full ladder algorithm is in Task 3.
- Semantic requirements (key): the stdin read happens at todo-resolution
  time — after the preflight, before the editor and the ask — once per
  creation; a TTY stdin is never read; the stdin-resolved todo carries the
  value-form semantics (verbatim content, one-trailing-newline
  normalization at the write, UTF-8, the same amendment hooks); every
  decision precedes the first mutation.
- Annotation context: `click` (publication ask, non-interactive
  detection), `editor-entry` (editor session), `topic-paths`,
  `refs-and-switching`, `checkpoints` (unchanged usage).

#### Cell `goga/commands/topics` (manifest: `goga/commands/topics/CODEMANIFEST`)

**Entity: `topics` (the click group), method `board`** — CHANGED
- Declared `location`: `topics.py`
- Method signature: `board(remote: bool = False, info: bool = False, host: tuple[str, ...] | None = None, per_host: bool = False, json_output: bool = False) -> exit_code: int`
- Change: two table views and the JSON form; `--json` + `--info` is a
  clean error before any git access; the default view collects the full
  inventory (no record filter — hosts lists need every hosting branch) and
  projects via `aggregate_topic_board`; the per-host view passes `host`
  into `collect_topic_board` as the record filter. Algorithm in Task 6.
- Annotation context: `topic-board` (from Imports), `click`,
  `beautiful_json`.

**Entity: `topics` (the click group), method `create`** — CHANGED
- Declared `location`: `topics.py`
- Method signature: `create(branch_name: str, todo: str | None = None, todo_from_stdin: bool = False, publish: bool = False, base_ref: str | None = None, from_current: bool = False, commit_message: str | None = None, switch: bool = False) -> exit_code: int`
- Change: maps the three states of the optional-value `--todo` option
  into `todo` / `todo_from_stdin` (algorithm step 5); no editor, no stdin
  read at this layer. Algorithm in Task 7.
- Annotation context: `creating` (from Imports), `publishing`,
  `project-configuration`, `click`.

**Routine: `render_topic_board`** — CHANGED (retargeted)
- Declared `location`: `render.py`
- Signature: `render_topic_board(entries: list[BoardEntry], width: int, info: bool = False)`
- Change: takes `list[BoardEntry]`; four-column default grid (topic,
  branch, hosts, statuses), five-column under `info` (todo between hosts
  and statuses). The hosts column header is the word `hosts`; the hosts
  names wrap whole onto continuation lines through the same greedy filler
  as the statuses. Width rules: `usable = width − 3·k`, every text column
  capped at `usable // k` (one quarter of usable at k=4, one fifth at
  k=5), statuses receives the remainder; all-min-8 below the narrow
  threshold (44 at k=4, 55 at k=5). Algorithm in Task 5.
- Annotation context: `click` (echo).

**Routine: `render_topic_host_rows`** — NEW (the moved body)
- Declared `location`: `render.py`
- Facade obligation: importable from `goga.commands.topics` (after Task 8), listed in `__all__`
- Signature: `render_topic_host_rows(records: list[BoardRecord], width: int, info: bool = False)`
- Semantic requirements: the per-host audit table — today's
  `render_topic_board` body moved unchanged in mechanics (`k = 4 if info
  else 3`; headers `(Topic, Branch, Statuses)` / `(Topic, Branch, todo,
  Statuses)`; "one third" / "one quarter" caps; narrow thresholds 33/44),
  with the docstring retitled to the audit view.
- Annotation context: `click` (echo).

**Routine: `render_board_json`** — NEW
- Declared `location`: `render.py`
- Facade obligation: importable from `goga.commands.topics` (after Task 8), listed in `__all__`
- Signature: `render_board_json(board: list[BoardEntry] | list[BoardRecord])`
- Semantic requirements: the machine-readable projection of either view —
  a `BoardEntry` shapes into `{topic, branch, hosts, statuses, current,
  remote, todo}`, a `BoardRecord` into the same without `hosts`; the todo
  key is a string or `null`, never omitted; `json.dumps(items, indent=4,
  sort_keys=True, ensure_ascii=False)` (`beautiful_json` verbatim) echoed
  with one trailing newline; empty board prints `[]`; read-only on `board`;
  the record shapes are a stable consumer contract (key order is not).
- Annotation context: `beautiful_json` (from Usages), `click` (echo).

### Re-exports

No DSL re-export blocks (`->Name: {}`) exist in either manifest. The
facade obligations are the Python-level ones (`__init__.py` `__all__`)
defined by the design's facade trace:

- `goga/topics/__init__.py`: extend the board import line to
  `BoardEntry, BoardRecord, aggregate_topic_board, collect_topic_board`;
  add `"BoardEntry"` and `"aggregate_topic_board"` to `__all__`
  (alphabetical) — Task 2.
- `goga/commands/topics/__init__.py`: export `render_topic_host_rows` and
  `render_board_json` beside `render_topic_board`; `__all__` grows to four
  names (alphabetical) — Task 8.

### Usages Context

- `convention` (`.goga/usages/conventions.md`, both cells): relative
  imports, `kw_only` frozen dataclasses, Google docstrings, CLI docstring
  rule (verbatim-rendered help, no Args/Returns/Raises), test structure
  (`tests/topics/`, `tests/commands/topics/`, `test_<module>.py` naming),
  mock-at-import-point discipline.
- `click` (`.goga/usages/cooks/click.md`, both cells): the CLI kit and
  the project patterns — groups, flags, the repeatable option
  (`multiple=True`; absent → `()`, emptiness tested, never `None`), the
  optional-value option (`is_flag=False, flag_value=<sentinel>,
  default=None`; three states; the reserved-sentinel rule — a module-level
  constant reserved by the command), `click.echo`, `click.ClickException`,
  `sys.stdin.isatty()` gates, `CliRunner` testing.
- `beautiful_json` (`.goga/usages/cooks/beautiful_json.md`,
  `goga/commands/topics`): `json.dumps(data, indent=4, sort_keys=True,
  ensure_ascii=False)` — the serialization form of `render_board_json`.

### Imported Usages

- `topic-board` from `goga/topics` (`goga/topics/.usages/topic-board.md`):
  the board contract of the domain (two projections, both filter
  semantics, the twin collapse, the winner rule) — shapes the `board`
  callback's delegation (Task 6). Updated by the apply stage; current.
- `creating` from `goga/topics` (`goga/topics/.usages/creating.md`): the
  creation contract with the acquisition ladder — shapes the `create`
  callback's mapping and help text (Task 7). Updated by the apply stage;
  current.
- `editor-entry` from `goga/topics/editor`
  (`goga/topics/editor/.usages/editor-entry.md`): the editor session
  protocol the ladder's editor rung relies on (cancellation → None) —
  Task 3.
- `topic-paths` from `goga/history`: slug normalization (the own-branch
  equality), year/tree-root patterns — Tasks 1, 3.
- `topic-statuses` from `goga/history`: scale assembly and maximal-status
  computation — Tasks 1 (collection + the aggregation's sort axis).
- `refs-and-switching` from `goga/topics/git`: the inventory, ref-tree
  reading, file reading without checkout — Task 1.
- `publishing` / `deleting` / `switching` / `todo-entry` from
  `goga/topics`: unchanged consumers referenced by the `create` /
  `delete` / `switch` callbacks (Tasks 6, 7 — unchanged paths).
- `project-configuration` from `goga/config`: the topics section schema
  for the lazy base/template resolution (Task 7 — unchanged path).
- `checkpoints` from `goga/config/hooks`: the config amendment checkpoint
  inside `_topics_section` (Task 7 — unchanged path).
- `registering-hooks` from `goga/topics`: the lifecycle events the group
  emits (the stdin todo passes through the same `amend_creation`
  checkpoint — Task 3).

### Local Usages

None. The design's `.usages/` Update section states: the three cell-level
usage files (`goga/topics/.usages/topic-board.md`,
`goga/topics/.usages/creating.md`,
`goga/commands/topics/.usages/topics-command.md`) were updated by the
apply stage and are current — no additions, no updates, no new files. The
project-level `.goga/usages/cooks/click.md` optional-value section is
likewise applied. **No task may modify any usage file or CODEMANIFEST.**

### External Dependencies

- `click` 8.5.0 — the optional-value semantics verified live by the
  design review: absent → `None`, bare `--todo` → the flag value, `--todo
  TEXT` → the text, empty → `""`; `multiple=True` absent → `()`;
  `is_flag=False` + `flag_value` keeps `secondary_opts` empty.
- `json` (stdlib) — `render_board_json`.
- `pytest` + `click.testing.CliRunner`, `io.TextIOWrapper(io.BytesIO(...))`
  stdin models — test infrastructure.
- The built-in nine-stage status scale (empty, todo, defined, discovered,
  backlog, designed, specified, planned, done) — the `builtin_scale`
  fixture pins it; `defined` (position 1) precedes `planned` (position 6)
  precedes `done` (position 8).

### Entity Interaction and Data Flow (verbatim from the design)

```
CLI goga topics board                        domain goga/topics
─────────────────────                        ─────────────────
topics.board(scope, remote, info,            collect_topic_board(year, remote, hosts)
                 host, per_host, json)  ───►   ├─ goga.history: current_year,
                 │                              │   assemble_status_scale (×2 — see
                 │                              │   aggregate), resolve_history_root,
                 │                              │   resolve_current_branch_name,
                 │                              │   normalize_topic_slug (working copy)
                 │                              └─ goga.topics.git: list_branch_refs,
                 │                                  read_ref_tree_paths, read_ref_file
                 │                              → list[BoardRecord]   (audit view)
                 ├─ default view ────────────► aggregate_topic_board(records, host)
                 │                              ├─ goga.history: normalize_topic_slug
                 │                              │  (branch-part → slug equality),
                 │                              │  assemble_status_scale (sort axis)
                 │                              └─ pure grouping/winning/sorting
                 │                              → list[BoardEntry]    (default view)
                 │
                 ├─ table, default ──────────► render_topic_board(entries, width, info)
                 ├─ table, --per-host ───────► render_topic_host_rows(records, width, info)
                 └─ --json ─────────────────► render_board_json(entries | records)
                                                └─ json.dumps(indent=4, sort_keys=True,
                                                   ensure_ascii=False) via beautiful_json

CLI goga topics create                       domain create_topic(..., todo_from_stdin)
──────────────────────                       ─────────────────────────────────────
topics.create(...)                           preflight (slug, occupancy, base)
  --todo TEXT   → todo="TEXT"                acquisition ladder:
  --todo        → todo_from_stdin=True   ──►   a. value → todo (stdin unread)
  absent/empty  → nothing                      b. non-TTY stdin read once → UTF-8 →
  (mapping in the callback)                        content test → 4 cases
  create_topic(name, base, todo,                 c. TTY stdin never read
               todo_from_stdin, ...)             d. editor on interactive terminal
                                                 e. path rules on unresolved todo
                                               publication ask (skipped for stdin todo)
                                               TopicHooks.amend_creation (every source)
                                               mutation path → topic_created
```

**Data flows:**

- **Default board view**: `topics.board` → `collect_topic_board(year,
  remote)` (no record filter — the full inventory is required to compute
  hosts lists) → `aggregate_topic_board(records, host)` (hosts-membership
  filter) → `render_topic_board(entries, width, info)` or
  `render_board_json(entries)`. Exit 0; empty board renders nothing as a
  table, `[]` as JSON.
- **Per-host audit view** (`--per-host`): `topics.board` →
  `collect_topic_board(year, remote, hosts=host)` (record filter — exact
  display-name equality) → `render_topic_host_rows(records, width, info)`
  or `render_board_json(records)` (records carry no `hosts` key).
- **Creation with piped todo**: `printf '…' | goga topics create NAME
  --todo --from-current` → callback maps the value-less `--todo` to
  `todo_from_stdin=True, todo=None` → `create_topic` preflight → stdin
  read once (bytes → strict UTF-8 → content test) → verbatim todo →
  amendment → mutation; no editor, no ask.
- **One collection pass, two views**: both consumer views derive from one
  `collect_topic_board` result; `aggregate_topic_board` only computes over
  the records (no git access).

**Entity dependencies:**

- `aggregate_topic_board` depends on `BoardRecord` and `BoardEntry`
  (same module) and on `normalize_topic_slug` + `assemble_status_scale`
  from `goga/history` (already imported in `board.py`).
- `render_topic_board` / `render_board_json` depend on `BoardEntry`
  (new import in `render.py`); `render_topic_host_rows` keeps
  `BoardRecord`.
- `topics.board` depends on both collectors and all three renderers.
- `topics.create` depends on the extended `create_topic` signature.
- Initialization order (design order): `board.py` entities first (the
  domain is the leaf of the CLI), then the `goga/topics` facade (the
  `BoardEntry` export `render.py` imports), then `render.py`, then
  `topics.py`, then the `goga/commands/topics` facade — realized as
  Tasks 1 → 2 → (3, 4) → 5 → 6 → 7 → 8 → 9.

## Facts

- Both CODEMANIFESTs already declare the target contracts (apply stage
  done; `goga lint` clean at 80 cells, 0 errors). They are read-only.
- `board.py` already imports `normalize_topic_slug` and
  `assemble_status_scale` from `goga/history`, and has the `_short_name`
  helper (`branch.partition("/")[2]`) the aggregation reuses.
- `render.py` already has `_column_widths(width, columns_count)`
  implementing the corrected equal-share rule (`usable = width − 3·k`,
  cap `usable // k`, statuses the remainder, all-min-8 below `k·8 + 3·k`)
  — generic over the column count; no width-arithmetic change is needed,
  only new column counts (4/5) and the hosts wrapping.
- `_wrap_segments(segments, cap)` is the greedy filler used for statuses;
  the hosts names wrap through the same filler as plain names (no
  brackets).
- `creation.py` already has `_write_todo` (one trailing newline, UTF-8),
  the amendment delivery, and the mutation paths — the ladder reuses them
  unchanged.
- The design's D1 contract fix (one quarter / one fifth) is already in the
  manifest; `_column_widths` satisfies it verbatim (re-verified by the
  design review by simulation).
- `aggregate_topic_board` assembles the scale internally as the sort axis
  only — a deliberate design decision (the entry sort key is the winner's
  first maximal status, which can differ from the input order); the
  assembly is not git access and its fatal `ImportError` wraps into the
  routine's clean-error boundary.
- The existing test harnesses: `_wire_board` (five board patch points in
  `goga.topics.board`), `builtin_scale` fixture, `_wire_creation` /
  `_editor_script` / `_tty` / `_non_interactive` (creation), `_TtyStdin`
  and `_topics_module` / `_topics_facade` resolvers (CLI), `capsys`
  renderers.
- The 9-stage scale floor: a record always has at least `["empty"]`, so
  `statuses[0]` in sort keys is never an index error.
- The scale is never cached across runs (platform rule) — the default
  view performs two assemblies per render (collection + aggregation), the
  accepted cost of the pure projection.

## Gap Analysis

- Missing contract entities: `BoardEntry`, `aggregate_topic_board`
  (`goga/topics/board.py`); `render_topic_host_rows`,
  `render_board_json` (`goga/commands/topics/render.py`).
- Missing facade exposure: `BoardEntry`, `aggregate_topic_board` on
  `goga/topics`; `render_topic_host_rows`, `render_board_json` on
  `goga/commands/topics`.
- API mismatches: `collect_topic_board` lacks `hosts`; `create_topic`
  lacks `todo_from_stdin`; `topics.board` lacks `host` / `per_host` /
  `json_output` and the view dispatch; `topics.create` lacks the
  three-state mapping and still treats a bare `--todo` as absent;
  `render_topic_board` takes `list[BoardRecord]` instead of
  `list[BoardEntry]`.
- Behavioral mismatches: `_resolve_todo` implements the old policy (no
  value + non-TTY → immediate clean error; no stdin read);
  `_publication_asked` lacks the came-from-stdin conjunct;
  `_LOCAL_TODO_ERROR` does not name the stdin source form; the `create`
  help docstring's "a value-less --todo is click's own usage error"
  wording is now false; the `board` callback renders one view only.
- Existing code that can be reused: `_short_name`, `_collapse_remote_twins`,
  `_marks_current`, the whole `_board_records` pipeline; `_column_widths`,
  `_row_line`, `_separator`, `_fit`, `_truncate`, `_wrap_segments`;
  `_write_todo`, `_draft_commit_message`, `_enter_fresh_branch`; both
  test harnesses.
- Test coverage gaps: every test named in the design's Test Stack Trace
  (see Tasks); existing tests needing expectation updates (not
  deletations): `test_collect_topic_board_signature` (+`hosts`),
  `test_create_topic_signature` (+`todo_from_stdin`),
  `test_entities_are_importable_from_the_cell_facade` (domain facade,
  +2 names), `test_facade_exports_two_names` (command facade, → 4 names),
  the old `render_topic_board` record-table tests (transfer to
  `render_topic_host_rows`), every `create_topic.assert_called_once_with`
  in the CLI tests (~12 sites — the `todo_from_stdin` positional slots in
  after `todo`), `test_board_callback_signature` (parameter list grows),
  `test_board_measures_the_terminal_width` (four-column grid: 44 wide at
  COLUMNS 40 and 30), `test_create_bare_todo_flag_is_usage_error`
  (value-less `--todo` is now a valid declaration — exit 0),
  `test_create_todo_option_surface` (docstring and the "no
  optional-value flag" comment rewritten to the three-state surface),
  `test_create_topic_todo_non_tty_clean_error` and the
  `_non_interactive` helper (the non-TTY stdin must model a real empty
  buffer — the ladder reads it).
- Missing visibility: none — both cells, their manifests, and the usage
  files are in the workspace and committed.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the next. Within each coding task, contract tests are written first (TDD workflow).

### Task 1: `board.py` — `BoardEntry`, `aggregate_topic_board`, and the `collect_topic_board` hosts filter (TDD coding)

This task implements the three entities of `goga/topics/CODEMANIFEST` with
`location: board.py`: the new `BoardEntry` data model, the new
`aggregate_topic_board` projection routine, and the `hosts` record filter
of `collect_topic_board`. Target file: `goga/topics/board.py`; tests:
`tests/topics/test_board.py`. The entity model mirrors the existing
`BoardRecord` (`@dataclass(frozen=True, kw_only=True)`, Google-docstring
Attributes). The aggregation is a pure projection: no git access, every
fact comes from the records; it groups the collected records by topic slug,
computes each topic's hosts list (collapsing a local branch and its remote
twin under the local name), finds the topic's own branch (the record whose
branch part normalizes into the slug via `normalize_topic_slug`), picks the
deterministic winner, and sorts by the winner's first maximal status. The
collection gains the exact display-name record filter after the twin
collapse, before the sort. `_short_name` already exists in the module.

Verified logical chain (from the design's code stack trace — transfer):

```
collect_topic_board(year, remote, hosts)
  steps 1–8 unchanged (year, scale, inventory, ref trees, statuses,
  todo summaries, twin collapse, current marking)
  → list[BoardRecord] unfiltered
  hosts filter: names = set(hosts);
                records = [r for r in records if r.branch in names]
                # exact display-name equality, union across values;
                # None and () both skip the filter;
                # unknown names yield [] (a filter, never an error)
  sort by (scale_order[statuses[0]], topic); return

aggregate_topic_board(records, hosts)
  1. scale_order = {stage.name: index for stage in
     assemble_status_scale().stages}        # the sort axis, assembled once
  2. groups = {} ; FOR r IN records: groups.setdefault(r.topic, []).append(r)
     → first-encounter order; the input list is never mutated or re-sorted
  3. FOR each (slug, group):
     a. local_names = {r.branch for r in group if not r.remote}
     b. hosts = sorted({r.branch for r in group
          if not (r.remote and _short_name(r.branch) in local_names)})
          # a local branch and its remote twin count once, under the local
     c. own = [r for r in group
          if normalize_topic_slug(r.branch if not r.remote
                                  else _short_name(r.branch)) == slug]
     d. IF own is empty: CONTINUE          # no own branch → no entry
     e. winner = min(own, key=lambda r: (not r.current, r.remote, r.branch))
     f. entries.append(BoardEntry(topic=slug, branch=winner.branch,
          hosts=hosts, statuses=winner.statuses,
          current=any(r.current for r in group),
          remote=winner.remote, todo=winner.todo))
  4. entries.sort(key=lambda e: (scale_order[e.statuses[0]], e.topic))
  5. IF hosts is not None and hosts:
     - names = set(hosts_arg)
     - entries = [e for e in entries if any(h in names for h in e.hosts)]
       # membership in the hosts list (not display-name equality — that is
       # the record filter); never resurrects a topic without an own branch
       # (the filter runs after the own-branch gate)
  6. return entries
```

Winner-rule note: `min(own, key=(not current, remote, branch))` — the
record hosting the current branch, otherwise a non-remote record over a
remote-tracking one, otherwise the first in the display-name alphabet. The
internal scale assembly (step 1) is a deliberate design decision: the entry
sort key is the *winner's* first maximal status, which can differ from the
first record's (the input order follows the least advanced host), so the
input order alone cannot sort the entries; the wrapper converts its fatal
`ImportError` into `click.ClickException` (the only handler — no git
boundary handlers needed). A record always has at least `["empty"]` (the
scale floor), so `statuses[0]` is never an index error.

**Usages relevant to this task:**
- `convention`: `from __future__ import annotations`; relative
  intra-package imports; `@dataclass(frozen=True, kw_only=True)`; Google
  docstrings; tests in `tests/topics/test_board.py`.
- `topic-paths` (from Imports): the slug normalization pattern —
  `normalize_topic_slug` decides own-branch membership ("release/1.3.0" →
  "release-1-3-0"; "origin/release/1.3.0" → short "release/1.3.0" → the
  same slug).
- `topic-statuses` (from Imports): the scale assembly — the aggregation's
  sort axis; `assemble_status_scale` is already imported in `board.py` for
  the collection.
- `refs-and-switching` (from Imports): the collection's unchanged
  inventory/tree/file-reading patterns.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (in `tests/topics/test_board.py`, expected to fail now): `BoardEntry` and `aggregate_topic_board` importable from `goga.topics.board`; `test_board_entry_is_frozen_kw_only_dataclass` — `@dataclass(frozen=True, kw_only=True)` (assert via `dataclasses` + the shared `is_kw_only_dataclass` helper from `tests.conftest`), `typing.get_type_hints(BoardEntry) == {"topic": str, "branch": str, "hosts": list[str], "statuses": list[str], "current": bool, "remote": bool, "todo": str | None}`, field order matches the signature, a positional call `BoardEntry("t", "b", ["h"], ["todo"], False, False)` raises `TypeError`, a frozen assignment raises `dataclasses.FrozenInstanceError`; a signature test for `aggregate_topic_board` — parameters `["records", "hosts"]`, both `POSITIONAL_OR_KEYWORD`, `hosts` defaults to `None`, hints `{"records": list[BoardRecord], "hosts": tuple[str, ...] | None, "return": list[BoardEntry]}`
- [x] **Contract tests**: update the existing `test_collect_topic_board_signature` — parameters grow to `["year", "remote", "hosts"]`, `hosts` defaults to `None`, hints become `{"year": str | None, "remote": bool, "hosts": tuple[str, ...] | None, "return": list[BoardRecord]}`
- [x] **Code**: add `BoardEntry` after `BoardRecord` in `goga/topics/board.py` — `@dataclass(frozen=True, kw_only=True)` with the seven declared fields (`todo: str | None = None` last), Google-docstring Attributes mirroring the `BoardRecord` style, per the declared property annotations
- [x] **Code**: add the public `aggregate_topic_board(records, hosts=None)` wrapper — mirrors `collect_topic_board`: `try: return _aggregate_board(records, hosts) except ImportError as exc: raise click.ClickException(str(exc)) from exc` — delegating to an internal unwrapped routine implementing the traced algorithm above (grouping dict in first-encounter order; hosts list; own-branch candidates; the `min` winner; the `BoardEntry` construction; the sort; the membership filter)
- [x] **Code**: extend `collect_topic_board` and `_board_records` with the `hosts: tuple[str, ...] | None = None` parameter — the filter `if hosts: names = set(hosts); records = [r for r in records if r.branch in names]` applied to the built records after `_collapse_remote_twins`, before the sort; update the two docstrings (the declared `hosts` parameter description and algorithm steps 9–10) to the contract wording
- [x] **Code**: update the `board.py` module docstring to the two-projection contract (the per-host records as the single source of facts; the aggregated default view) — it is a contract mirror, not narration
- [x] **Interface verification**: `python -m pytest tests/topics/test_board.py -k "Contract or board_entry or aggregate" -x` — the contract tests pass (facade-level importability arrives in Task 2; here the entities import from `goga.topics.board`)
- [x] **Logic tests** (positive): `test_collect_topic_board_filters_records_by_exact_host_names` — `_wire_board` base scenario (inventory `feat/a` local, `origin/feat/a`, `origin/feat/b` remote, `main` local; trees hosting feat-a plan.md on `feat/a` and its twin, feat-b prd.md on `origin/feat/b`; current `feat/a`; no todo files); `collect_topic_board(hosts=("main", "origin/feat/b"))` → `[(r.topic, r.branch) for r in records] == [("feat-b", "origin/feat/b")]` (the twin row `feat-a@feat/a` drops — exact display-name equality, union across values)
- [x] **Logic tests** (positive): `test_collect_topic_board_empty_hosts_keeps_every_record` — `hosts=None` and `hosts=()` both return the full twin-collapsed inventory `[("feat-b", "origin/feat/b"), ("feat-a", "feat/a")]` (scale order: defined precedes planned, as the existing suite pins)
- [x] **Logic tests** (positive): `test_aggregate_topic_board_one_entry_per_topic_with_own_branch` — records built directly (no git; patch `board.assemble_status_scale` with the `builtin_scale` fixture for the sort axis): `BoardRecord("feat-a", "feat/a", ["planned"], True, False, "Fix.")`, `BoardRecord("feat-a", "origin/feat/a", ["planned"], False, True, "Fix.")`, `BoardRecord("release-1-3-0", "main", ["done"], False, False, None)`, `BoardRecord("release-1-3-0", "origin/release/1.3.0", ["done"], False, True, None)`; `aggregate_topic_board(records)` → `[(e.topic, e.branch, e.hosts, e.remote) for e in entries] == [("feat-a", "feat/a", ["feat/a"], False), ("release-1-3-0", "origin/release/1.3.0", ["main", "origin/release/1.3.0"], True)]`; `entries[0].statuses == ["planned"]`; `entries[0].todo == "Fix."`; `entries[0].current is True`; `entries[1].todo is None`
- [x] **Logic tests** (positive): `test_aggregate_topic_board_merged_only_topic_produces_no_entry` — one group `BoardRecord("old-work", "main", ["done"], False, False, None)` ("main" does not normalize to "old-work") → `entries == []`
- [x] **Logic tests** (positive): `test_aggregate_topic_board_own_branch_collision_winner_order` — three parametrized cases over the topic `feature-x` with own branches colliding (every branch spelling normalizes into the slug: `Feature X` → `feature-x`, `feature_x` → `feature-x`, `origin/feature-x` → short `feature-x` → `feature-x`): (a) `feature_x` (current, non-remote) vs `origin/feature-x` (not current, remote) → `feature_x` wins; (b) `Feature X` (not current, non-remote) vs `origin/feature-x` (remote) → `Feature X` wins; (c) `feature_x` vs `Feature X`, both non-remote, neither current → `Feature X` wins (display-name alphabet — uppercase sorts before lowercase); assert `entries[0].branch` per case
- [x] **Logic tests** (positive): `test_aggregate_topic_board_sorts_by_winner_statuses_scale_order` — input already in the collection's order (the least advanced host of each topic first): `BoardRecord("zzz", "zzz", ["planned"], False, False, None)`, `BoardRecord("aaa", "aaa", ["todo"], False, False, None)` (the own branch), `BoardRecord("aaa", "z-host", ["planned"], False, False, None)` (a merged host more advanced than the own branch) → `[e.topic for e in entries] == ["aaa", "zzz"]`; `entries[0].statuses == ["todo"]` (the output sort is computed from the winner's statuses — not inherited from the input order)
- [x] **Logic tests** (positive): `test_aggregate_topic_board_hosts_filter_union_and_no_resurrection` — the merged-host scenario above plus a merged-only topic `old-work` on `main`; `aggregate_topic_board(records, hosts=("main",))` → `[e.topic for e in entries] == ["release-1-3-0"]` (the own-branch gate runs first — old-work drops; the filter keeps entries whose hosts contain "main")
- [x] **Logic tests** (positive): `test_aggregate_topic_board_is_read_only_over_records` — snapshot copy taken before; `aggregate_topic_board(records, hosts=("feat/a",))` → `records == snapshot` element-wise and order
- [x] **Logic tests** (positive): `test_aggregate_topic_board_empty_records_yield_empty_list` — `aggregate_topic_board([])` → `[]`
- [x] **Logic tests** (negative): `test_aggregate_topic_board_scale_import_error_is_clean` — patch `board.assemble_status_scale` to raise `ImportError("broken tool")`; `aggregate_topic_board([record])` → `pytest.raises(click.ClickException)` with "broken tool" in the message
- [x] **Logic tests** (edge): `test_aggregate_topic_board_unknown_host_yields_empty` — `aggregate_topic_board(records, hosts=("no-such-branch",))` → `entries == []`, no error
- [x] **Logic tests** (edge): `test_collect_topic_board_remote_mode_host_filter_uses_remote_names` — `_wire_board` in remote mode (current `None`), inventory with `origin/feat/a`; `collect_topic_board(remote=True, hosts=("feat/a",))` → `[]`; with `hosts=("origin/feat/a",)` the row returns
- [x] **Debugging**: `python -m pytest tests/topics/test_board.py -x` — fix implementation code until all tests pass (do NOT fix test code; do not weaken assertions)
- [x] **Contract re-verification**: facade/module API shape (`BoardEntry` constructor fields, `aggregate_topic_board` and `collect_topic_board` signatures), behavior per the declared annotations (read-only projection, filter semantics, winner rule, sort axis), `goga/topics` unchanged for every other entity
- [x] **Lint**: `ruff check goga/topics/board.py` — fix formatting, apply decomposition if necessary

### Task 2: `goga/topics` facade — export `BoardEntry` and `aggregate_topic_board` (infrastructure)

This task completes the facade obligation of the `goga/topics` cell: the
new board entities must be importable from the package root and listed in
`__all__`. This export is a dependency of `goga/commands/topics/render.py`
(Task 5 imports `BoardEntry` from `...topics`). Target file:
`goga/topics/__init__.py`; tests: `tests/topics/test_board.py` (the
facade contract test).

**Usages relevant to this task:**
- `convention`: the facade is `__init__.py` with `__all__`; alphabetical
  order; the module docstring is a contract mirror.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Extend the board import line in `goga/topics/__init__.py` to `from .board import BoardEntry, BoardRecord, aggregate_topic_board, collect_topic_board`
- [x] Add `"BoardEntry"` (before `"BoardRecord"`) and `"aggregate_topic_board"` (first among the lowercase names, before `"check_branch_occupancy"`) to `__all__` — alphabetical order preserved
- [x] Update the `goga/topics/__init__.py` module docstring to the new contract (the inventory in two projections — the per-host audit records as the source of facts and the aggregated one-entry-per-topic view; the creation's todo acquisition ladder — value, declared stdin, editor, clean error) — a contract mirror, not narration
- [x] Update the existing facade contract test `test_entities_are_importable_from_the_cell_facade` in `tests/topics/test_board.py` — assert `cell.BoardEntry is BoardEntry`, `cell.aggregate_topic_board is aggregate_topic_board`, `"BoardEntry" in cell.__all__`, `"aggregate_topic_board" in cell.__all__` (importing the two names from `goga.topics.board` as the test does today for `BoardRecord`/`collect_topic_board`)
- [x] Verify facade accessibility: `python -c "from goga.topics import BoardEntry, aggregate_topic_board"` and `python -m pytest tests/topics/test_board.py -k Contract -x`
- [x] Lint: `ruff check goga/topics/__init__.py` — fix formatting if necessary

### Task 3: `creation.py` — the `create_topic` todo acquisition ladder (TDD coding)

This task implements the changed `create_topic` of
`goga/topics/CODEMANIFEST` (`location: creation.py`): the `todo_from_stdin`
parameter and the acquisition ladder — the explicit value, else the declared
stdin source, else the interactive editor, else the clean path rules. Target
file: `goga/topics/creation.py`; tests: `tests/topics/test_creation.py`.
The preflight, the amendment delivery, and the mutation paths keep their
traced shapes; the stdin-resolved todo flows through the same
`amend_creation` and the same `_write_todo` as a value or an editor text
(value-form semantics). The domain reads stdin exactly once via
`sys.stdin.buffer.read()` behind the `not sys.stdin.isatty()` guard, decodes
strictly, and converts `UnicodeDecodeError` **at the decode site** (it is a
`ValueError` subclass and would otherwise pierce the wrapper's clean-error
boundary).

The ladder (from the design's algorithm design and code stack trace —
transfer):

```
_resolve_todo(todo, todo_from_stdin) -> (todo | None, came_from_stdin):
1. IF todo: RETURN (todo, False)            # stdin stays unread
2. IF not sys.stdin.isatty():
   a. data = sys.stdin.buffer.read()        # fully, exactly once
   b. TRY content = data.decode("utf-8")
      EXCEPT UnicodeDecodeError: clean error naming the todo option
   c. has_content = content.strip() != ""   # whitespace decides only;
                                            # the content is never trimmed
   d. IF todo_from_stdin and has_content:
        RETURN (content, True)              # verbatim; no editor, no ask
   e. IF not todo_from_stdin and has_content:
        clean error naming the todo option  # piped content is never
                                            # silently ignored
   f. fall through to the editor rung       # declared+bare, or
                                            # undeclared+bare
3. RETURN (edit_text() if sys.stdin.isatty() else None, False)

then, in _create_topic (the path rules, after the ladder):
4. IF publish and todo is None: clean error asking for the todo
5. IF not publish and not switch and todo is None:
   the local-todo clean error (names the todo sources — value, piped
   stdin — and the switch form)
6. publication ask: only when (not publish) and todo is not None and
   came_from_stdin is False and sys.stdin.isatty()
7. amendment and mutation paths unchanged; the stdin todo flows through
   the same amend_creation and the same _write_todo (one trailing
   newline, UTF-8)
```

Trace checkpoints already verified by the design (keep them true): the
stdin read happens after the preflight; a TTY stdin is never read (the
read sits behind the `not isatty()` branch); a non-interactive terminal
without declaration and without content leaves no todo (the old
unconditional clean error is gone — the path rules decide); the editor
rung checks `isatty()` before `edit_text()`; every decision precedes the
first mutation. `_publication_asked` gains the `came_from_stdin` fact.
`_LOCAL_TODO_ERROR` is extended to name the stdin source form alongside
the value form and the switch flag.

**Usages relevant to this task:**
- `convention`: Google docstrings; the test stdin models below; tests in
  `tests/topics/test_creation.py`.
- `click` (from Usages): the publication ask (`click.confirm`), the
  non-interactive detection (`sys.stdin.isatty()`),
  `click.ClickException` for the clean errors.
- `editor-entry` (from Imports): the editor session protocol of rung d —
  `edit_text()` cancellation leaves no todo.
- `checkpoints` (from Imports): the stdin todo passes through the same
  `amend_creation` checkpoint as every other source.
- `topic-paths` (from Imports): the slug, directory, and todo-file path
  patterns of the unchanged preflight and mutation shapes.
- `refs-and-switching` (from Imports): the checkout pattern of the
  unchanged switch path.
- Stdin modeling for the tests (the design's general setup): monkeypatch
  `sys.stdin` with `io.TextIOWrapper(io.BytesIO(b"..."))` — it exposes
  `.buffer` and reads `isatty()` as False; a `tty` variant subclasses the
  wrapper with `isatty() -> True` to prove the buffer is never read (for
  the never-read proof, a `MagicMock` buffer whose any read fails the
  test).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: update the existing `test_create_topic_signature` in `tests/topics/test_creation.py` — the parameter list grows to `["branch_name", "base_ref", "todo", "todo_from_stdin", "publish", "commit_message", "year", "switch"]` (POSITIONAL_OR_KEYWORD, `todo_from_stdin` default `False`, hints `todo_from_stdin: bool`); re-verify `create_topic` importability from `goga.topics` (already exported — unchanged)
- [x] **Code**: extend the public `create_topic` signature and the `_create_topic` mirror with `todo_from_stdin: bool = False` directly after `todo`; thread the declaration into the todo resolution; update the docstrings (Args, the ladder algorithm, Requirements — the contract wording: the stdin read at todo-resolution time, once per creation, a TTY stdin never read, the value-form semantics of the stdin-resolved todo, the ask skip)
- [x] **Code**: rewrite `_resolve_todo(todo, todo_from_stdin) -> tuple[str | None, bool]` per the traced ladder (returns the todo and the came-from-stdin fact; the four stdin cases of rung b; the decode-site `UnicodeDecodeError` → `click.ClickException` naming the todo option; rung c/d: `edit_text()` only when `sys.stdin.isatty()`, else `None`)
- [x] **Code**: extend `_publication_asked(publish, todo, came_from_stdin)` — asks only when `not publish and todo is not None and came_from_stdin is False and sys.stdin.isatty()`
- [x] **Code**: keep the path rules after the ladder (`publish` + todo None → the clean ask-for-todo error; `not publish and not switch` + todo None → `_LOCAL_TODO_ERROR`; `switch` tolerates None) and extend `_LOCAL_TODO_ERROR` to name the stdin source form alongside the value form and the switch flag
- [x] **Code**: update the `creation.py` module docstring to the ladder contract (value → declared stdin → editor → clean error; the publication ask skipped when the todo came from stdin)
- [x] **Interface verification**: `python -m pytest tests/topics/test_creation.py -k Contract -x` — the contract tests pass
- [x] **Logic tests** (test harness update first): update the `_non_interactive` helper to `monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"")))` — a non-TTY stdin with a real empty `.buffer` (the ladder reads it; the old bare `mock.Mock` had no honest buffer); add stdin-model helpers per the design: a non-TTY wrapper over `BytesIO(b"...")` for piped content and a TTY variant subclassing the wrapper with `isatty() -> True`
- [x] **Logic tests** (positive): `test_create_topic_todo_value_wins_over_piped_stdin` — `sys.stdin` = `TextIOWrapper(BytesIO(b"piped\n"))` whose `.buffer.read` is wrapped in a `mock.MagicMock` delegate counting reads; `create_topic("Feature/Foo", "HEAD", todo="Value.", switch=True)` → the buffer-read mock call count is 0; the result line reports the creation; `todo.md` content is `"Value.\n"`
- [x] **Logic tests** (positive): `test_create_topic_todo_from_stdin_with_content` — `sys.stdin` = `TextIOWrapper(BytesIO(b"First\nSecond\n"))`; `edit_text` patched to a `MagicMock` (must not be called); `click.confirm` patched (must not be called); `create_topic("Feature/Foo", "HEAD", todo_from_stdin=True, switch=True)` → `todo.md` content `"First\nSecond\n"` (already ends in one newline — kept); `edit_text` not called; `confirm` not called; the result line is the creation line
- [x] **Logic tests** (positive): `test_create_topic_publication_ask_skipped_when_todo_came_from_stdin` — non-TTY stdin `TextIOWrapper(BytesIO(b"First\n"))` carrying content; `publish=False`, `switch=False`; `confirm` patched to a MagicMock that would return True; `create_topic("Feature/Foo", "HEAD", todo_from_stdin=True)` (default path) → `confirm` not called; the quarantined commit exists on the branch with the stdin todo (the `wired.plant` touchpoint records it)
- [x] **Logic tests** (positive): `test_create_topic_amendment_receives_stdin_todo` — the harness + `recording_hooks` subscribing `amend_creation` and `topic_created`; `sys.stdin` with content; `create_topic("Feature/Foo", "HEAD", todo_from_stdin=True, switch=True)` → the recorded `amend_creation` context's todo is the verbatim piped text; `topic_created` fired exactly once with `checked_out=True`
- [x] **Logic tests** (negative): `test_create_topic_piped_content_without_declaration_is_clean_error` — `sys.stdin` = `TextIOWrapper(BytesIO(b"piped content\n"))`; `edit_text` patched (must not run); `create_topic("Feature/Foo", "HEAD", switch=True)` (no value, no declaration, non-TTY stdin with content — only the content rule can fail) → `pytest.raises(click.ClickException)` with a message naming `--todo`; the branch was never created; the editor mock not called
- [x] **Logic tests** (negative): `test_create_topic_stdin_non_utf8_is_clean_error` — `sys.stdin` = `TextIOWrapper(BytesIO(b"\xff\xfe\n"))`; `create_topic("Feature/Foo", "HEAD", todo_from_stdin=True, switch=True)` → `pytest.raises(click.ClickException)` with a message naming the todo option; no branch, no directory
- [x] **Logic tests** (negative): `test_create_topic_headless_no_switch_without_todo_is_local_todo_error` — non-TTY stdin with an empty pipe, no declaration, no value, `switch=False`, `publish=False`; `create_topic("Feature/Foo", "HEAD")` → `click.ClickException` whose message names the todo sources (value, piped stdin) and the switch form; nothing mutated
- [x] **Logic tests** (edge): `test_create_topic_tty_stdin_never_read` — a stdin wrapper with `isatty() -> True` whose `.buffer` is a `MagicMock` (any read fails the test); `edit_text` patched to return `"Editor text."`; `create_topic("Feature/Foo", "HEAD", switch=True)` → the buffer mock has no reads; `todo.md` content is `"Editor text.\n"`
- [x] **Logic tests** (edge): `test_create_topic_declared_bare_stdin_falls_to_editor` — a TTY stdin model (`isatty() -> True`) whose `.buffer` is a mock failing the test on any read (the declaration with a TTY stdin never reads either); `edit_text` patched to return `"Typed."`; `create_topic("Feature/Foo", "HEAD", todo_from_stdin=True, switch=True)` → `todo.md` content `"Typed.\n"`
- [x] **Logic tests** (edge): `test_create_topic_whitespace_only_stdin_counts_as_bare` — `sys.stdin` = `TextIOWrapper(BytesIO(b"\n  \t\n"))`; `edit_text` patched to a `MagicMock`; `create_topic("Feature/Foo", "HEAD", todo_from_stdin=True, switch=True)` → `edit_text` not called (the editor rung checks the terminal first — non-TTY); no `todo.md` file in the topic directory; the result line reports the creation (a regression to a byte-emptiness check would raise the never-ignored clean error here — the pipe carries non-empty bytes — and fail this test)
- [x] **Logic tests** (existing-test update): review and update `test_create_topic_todo_non_tty_clean_error` to the ladder world — with the updated `_non_interactive` (empty pipe, no declaration) the rungs leave no todo and the error becomes the local-todo path error of the no-switch path; either retarget it to the piped-content rule (stdin carrying content without declaration) or fold it into `test_create_topic_piped_content_without_declaration_is_clean_error` — no coverage of the old immediate-error policy may remain as such; re-run every other `_non_interactive`-using test (`test_create_topic_publish_without_todo_error` and kin) and confirm the empty-pipe model keeps their traced outcomes
- [x] **Debugging**: `python -m pytest tests/topics/test_creation.py -x` — fix implementation code until all tests pass (do NOT fix test code; do not weaken assertions)
- [x] **Contract re-verification**: the `create_topic` signature matches the manifest (positional order `todo_from_stdin` after `todo`); every pre-existing handler of the wrapper unchanged; every requirement of the declared algorithm holds (the ladder order, the once-only read, the TTY guard, the ask skip, the value-form write semantics, the amendment coverage)
- [x] **Lint**: `ruff check goga/topics/creation.py` — fix formatting, apply decomposition if necessary

### Task 4: Integration tests — the domain board pipeline (collect → aggregate) (integration tests)

This task verifies the cross-entity data flow of the `goga/topics` board
entities: both board views derive from **one** `collect_topic_board`
result, and `aggregate_topic_board` only computes over the records (no git
access). Scope: `collect_topic_board` + `aggregate_topic_board` composed
over the existing `_wire_board` monkeypatch harness (the real git boundary
mocked at the import points in `goga.topics.board`; the `builtin_scale`
fixture; the working-copy setup via `tmp_path` + `monkeypatch.chdir`).
Tests are added to `tests/topics/test_board.py` (a new
`TestBoardPipeline` class — the `test_<module>.py` naming convention
keeps them in the board module's file).

**Usages relevant to this task:**
- `convention`: the test structure, the mock-at-import-point discipline,
  the `builtin_scale` fixture.
- `topic-board` (imported usage, consumer side): the two projections and
  both filter semantics — the composition this task pins.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Add the `TestBoardPipeline` class to `tests/topics/test_board.py`
- [x] Test cross-entity interaction: the default view over the base scenario — `monkeypatch.chdir(tmp_path)`, `_working_copy_topic(tmp_path, "2026", "feat-a", ["plan.md"])`, `_wire_board(monkeypatch, builtin_scale, _base_inventory(), _base_trees(), "feat/a")`; `records = collect_topic_board("2026")` then `entries = aggregate_topic_board(records)` → the records are the traced twin-collapsed inventory (`[("feat-b", "origin/feat/b", ["defined"], False, True, None), ("feat-a", "feat/a", ["planned"], True, False, None)]`); the entries are `[("feat-b", "origin/feat/b", ["origin/feat/b"], ...remote=True...), ("feat-a", "feat/a", ["feat/a"], ...current=True...)]` in that order (defined, scale position 1, precedes planned, position 6); `entries[0].remote is True`; `entries[1].current is True`; `entries[1].statuses == ["planned"]`
- [x] Test cross-entity interaction: the record filter composes with the projection — `records = collect_topic_board("2026", hosts=("origin/feat/b",))` (the record filter travels into the collection) then `aggregate_topic_board(records)` → exactly one entry: topic `feat-b`, branch `origin/feat/b`, hosts `["origin/feat/b"]`, remote True
- [x] Test edge case: the entry filter over the full inventory — `aggregate_topic_board(collect_topic_board("2026"), hosts=("feat/a",))` → exactly one entry (`feat-a`, branch `feat/a`, hosts `["feat/a"]`); with `hosts=("no-such-branch",)` → `[]` (a filter, never an error)
- [x] Run validation: `python -m pytest tests/topics/test_board.py -x`

### Task 5: `render.py` — the three renderers (TDD coding)

This task implements the three entities of
`goga/commands/topics/CODEMANIFEST` with `location: render.py`: the
retargeted `render_topic_board` (the default-view table over
`list[BoardEntry]`), the new `render_topic_host_rows` (the per-host audit
table — the moved body of today's `render_topic_board`, mechanics
identical, docstring retitled), and the new `render_board_json` (the
machine-readable projection of either view). Target file:
`goga/commands/topics/render.py`; tests:
`tests/commands/topics/test_render.py`. The width arithmetic needs no
change — the existing `_column_widths(width, columns_count)` already
implements the corrected equal-share rule; only the column counts and the
hosts wrapping are new. `render.py` gains the `BoardEntry` import from
`...topics` (available after Task 2) and the `json` import.

The default-grid algorithm (from the design — transfer):

```
render_topic_board(entries, width, info):
1. IF not entries: return
2. k = 5 if info else 4; caps = _column_widths(width, k)
   # usable = width − 3k; text columns usable//k (one quarter at k=4,
   # one fifth at k=5); statuses the remainder;
   # all columns 8 when usable < 8k  (thresholds: 44 at k=4, 55 at k=5)
3. header = (Topic, Branch, hosts, Statuses) or (Topic, Branch, hosts,
   todo, Statuses); echo header row and separator
4. FOR entry IN entries:
   a. topic_text = "* " + entry.topic if entry.current else entry.topic
   b. host_lines = _wrap_segments(list(entry.hosts), hosts_cap)
      status_lines = _wrap_segments([f"[{s}]" for s in entry.statuses],
                                    statuses_cap)
   c. FOR i IN range(max(len(host_lines), len(status_lines), 1)):
        leading = (topic_text, entry.branch[, entry.todo or ""])
        cells = leading pieces (first line only) + host_lines[i] or ""
                + ([todo already in leading] +) status_lines[i] or ""
        echo _row_line(cells, caps)
   d. echo separator (the row divider)

render_board_json(board):
1. items = []
   FOR item IN board:
     IF isinstance(item, BoardEntry):
       items.append({"topic": ..., "branch": ..., "hosts": item.hosts,
         "statuses": ..., "current": ..., "remote": ...,
         "todo": item.todo})
     ELSE:
       items.append({"topic": ..., "branch": ..., "statuses": ...,
         "current": ..., "remote": ..., "todo": item.todo})
2. click.echo(json.dumps(items, indent=4, sort_keys=True,
   ensure_ascii=False))
```

Design facts to keep: the hosts column header is the word `hosts`; the
hosts wrap whole onto continuation lines through the same greedy filler as
the statuses (plain names, no brackets); the row line count is
`max(len(host_lines), len(status_lines), 1)` with continuation lines
carrying the earlier columns empty; a row divider closes every record, the
last included; a `todo` of None/empty renders an empty cell; the remote
prefix of a remote own branch stays visible in the branch column; the
table never exceeds `width` except below the narrow threshold (44/55);
overlong host or status names truncate with the single ellipsis inside the
filler. `render_board_json` is homogeneous by construction (one view per
call), read-only on `board`, prints nothing outside the JSON array.

**Usages relevant to this task:**
- `convention`: Google docstrings; renderer tests build plain
  `BoardRecord` / `BoardEntry` instances and are `COLUMNS`-independent
  (the width is a direct argument); output captured with `capsys`.
- `click` (from Usages): `click.echo` for all output.
- `beautiful_json` (from Usages): `json.dumps(items, indent=4,
  sort_keys=True, ensure_ascii=False)` then one `click.echo` — the
  trailing newline and the plain-stream behavior come from echo.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (in `tests/commands/topics/test_render.py`, expected to fail now): `render_topic_host_rows` and `render_board_json` importable from `goga.commands.topics.render` and callable (`render.render_topic_host_rows is ...`, mirror the existing facade-identity style at module level; the cell-facade export arrives in Task 8); update `test_render_topic_board_signature` — parameters stay `["entries", "width", "info"]`, hints become `{"entries": list[BoardEntry], "width": int, "info": bool, "return": type(None)}`; new signature tests — `render_topic_host_rows`: `["records", "width", "info"]`, hints `{"records": list[BoardRecord], "width": int, "info": bool, "return": type(None)}`; `render_board_json`: `["board"]`, hints `{"board": list[BoardEntry] | list[BoardRecord], "return": type(None)}`
- [x] **Code**: extend the import to `from ...topics import BoardEntry, BoardRecord`; add `import json`
- [x] **Code**: move today's `render_topic_board` body to the new `render_topic_host_rows(records, width, info=False)` — mechanics identical (`columns_count = 4 if info else 3`, headers `(Topic, Branch, Statuses)` / `(Topic, Branch, todo, Statuses)`, wrapped statuses, row dividers, current marker, empty → nothing); retitle its docstring to the audit view (one row per topic and hosting branch)
- [x] **Code**: write the new `render_topic_board(entries, width, info=False)` per the traced algorithm — the four/five-column grid with the hosts column, the hosts wrapping through `_wrap_segments`, the todo column between hosts and statuses under `info`, the docstring mirroring the declared annotation (width rules "one quarter"/"one fifth" of usable, thresholds 44/55)
- [x] **Code**: write `render_board_json(board)` per the traced algorithm — the `isinstance(item, BoardEntry)` discrimination, the `todo` key always present (`null` or string), the `beautiful_json` serialization, one `click.echo`
- [x] **Code**: update the `render.py` module docstring to the three-renderer contract (the default-view table, the audit table, the JSON projection — pure output, the records/entries print as given) and the `test_render.py` module docstring accordingly
- [x] **Interface verification**: `python -m pytest tests/commands/topics/test_render.py -k Contract -x`
- [x] **Logic tests** (existing-test transfer): move the record-table scenario tests of the old `render_topic_board` (the `TestRenderTopicBoard`, `TestRenderTopicBoardInfo`, `TestRenderTopicBoardRowDividers` scenarios — widths/wrap, current asterisk, degenerate narrow terminal, boundary widths 33/32 and 44/43, two-segments-one-line, todo header, None-todo empty cell, continuation lines, row dividers) onto `render_topic_host_rows` — rename the call sites, keep the golden expectations identical (3/4-column grids, "one third"/"one quarter" caps, thresholds 33/44)
- [x] **Logic tests** (positive): `test_render_topic_board_default_four_columns_with_hosts` — one `BoardEntry("feat-a", "feat/a", ["feat/a", "main", "release/1.3.0"], ["planned"], True, False, "Fix.")`; `render_topic_board([entry], 100)` → header line `| Topic | Branch | hosts | Statuses |` padded to caps (22 each); the `* feat-a` marker in the topic cell; the hosts cell text spans two grid lines ("feat/a main" + "release/1.3.0" — the joined names are 26 chars > 22) with the earlier columns empty on the second; one row divider after the record (the last included); every line ≤ 100 columns
- [x] **Logic tests** (positive): `test_render_topic_board_info_five_columns_order` — the same entry; `render_topic_board([entry], 120, info=True)` → header cells in order `Topic, Branch, hosts, todo, Statuses` (caps 21 each); the todo cell `"Fix."`; a `None`-todo parametrization renders an empty cell
- [x] **Logic tests** (positive): `test_render_topic_board_width_rules_quarter_and_fifth` — parametrized: one entry at width 100 (default, k=4) and 125 (info, k=5); the header separator dash runs equal the computed caps (usable(100,4)=88 → 22 each → dash runs 24; usable(125,5)=110 → 22 each → dash runs 24); at widths 43 (k=4) and 54 (k=5) every dash run is 10 (8+2 padding — the all-min-8 floor)
- [x] **Logic tests** (positive): `test_render_topic_host_rows_matches_established_layout` — the transferred golden expectations above (the rename must not change the audit layout)
- [x] **Logic tests** (edge): `test_render_board_json_empty_board` — `render_board_json([])` → the captured output is exactly `"[]\n"` (one trailing newline); also pin the non-empty shapes at renderer level: one `BoardEntry` → `json.loads` of the output equals `{"topic": "feat-a", "branch": "feat/a", "hosts": ["feat/a", "main"], "statuses": ["planned"], "current": True, "remote": False, "todo": "Fix."}` and one `BoardRecord` → the same without the `hosts` key (`todo` present) — `sort_keys=True`, `indent=4` (the output starts with `"[\n    {"`)
- [x] **Debugging**: `python -m pytest tests/commands/topics/test_render.py -x` — fix implementation code until all tests pass (do NOT fix test code; do not weaken assertions)
- [x] **Contract re-verification**: the three signatures and behaviors match the manifest (hosts header wording, todo placement, width fractions, divider rules, JSON key sets, read-only constraints)
- [x] **Lint**: `ruff check goga/commands/topics/render.py` — fix formatting, apply decomposition if necessary

### Task 6: `topics.py` — the `board` subcommand surface (TDD coding)

This task implements the changed `board` method of the `topics` group
(`goga/commands/topics/CODEMANIFEST`, `location: topics.py`): the
repeatable `--host` option, the `--per-host` flag, the `--json` flag, the
two-view dispatch, and the `--json --info` mutual exclusion. Target file:
`goga/commands/topics/topics.py`; tests:
`tests/commands/topics/test_topics.py`. The callback algorithm (from the
design — transfer):

```
1. IF json_output and info: clean error ("--json --info" — the todo is
   always present in the JSON records)
2. IF not per_host:
     records = collect_topic_board(scope.year, remote)
     entries = aggregate_topic_board(records, host)
   ELSE:
     records = collect_topic_board(scope.year, remote, hosts=host)
3. IF json_output: render_board_json(entries if not per_host else
   records)
   ELSE:
     width = shutil.get_terminal_size().columns
     IF not per_host: render_topic_board(entries, width, info)
     ELSE: render_topic_host_rows(records, width, info)
4. ctx.exit(0)
```

Option surfaces: `--remote/-r` and `--info/-i` flags (unchanged); `--host`
— `multiple=True`, **no short form** (`-h` is click's help), help text
documenting exact display-name match and the union across values;
`--per-host` — flag; `--json` — flag bound to the Python name
`json_output`. Edge cases: empty board → nothing as a table, `[]` as
JSON, exit 0; an unknown `--host` name → the empty board, never an error;
`--host` composes with `--remote`, `--per-host`, and `--json`. No git,
editor, or stdin access at this layer. The delegation order matters: the
default view collects the **full** inventory (no record filter — hosts
lists need every hosting branch) and hands `host` to
`aggregate_topic_board` only.

**Usages relevant to this task:**
- `click` (from Usages): the repeatable option (`multiple=True`; tuple
  semantics — click's absent option delivers `()`, which the domain reads
  as no filter; emptiness tested, never a `None` check), the flags,
  `click.echo`/`click.ClickException`, exit-code propagation.
- `topic-board` (from Imports): the board contract of the domain — both
  projections and both filter semantics; shapes the delegation.
- `beautiful_json` (from Usages): reached through `render_board_json`.
- `convention`: the CLI docstring rule (verbatim-rendered help docstring,
  no Args/Returns/Raises); `CliRunner` tests with the domain mocked at
  its import site (`_topics_module`); a pinned `COLUMNS` keeps the
  terminal width deterministic.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: update the existing `test_board_callback_signature` — the parameter list grows to `["scope", "remote", "info", "host", "per_host", "json_output"]` with the flag defaults `False` and `host` defaulting to the empty tuple (click's `multiple=True` semantics); add option-surface tests mirroring the existing flag tests — `test_board_carries_the_host_option` (an `--host` `click.Option` with `multiple=True`, no short form, default `()`), `test_board_carries_the_per_host_flag`, `test_board_carries_the_json_flag` (the option's Python name is `json_output`)
- [x] **Code**: extend the imports — `aggregate_topic_board` from `...topics`; `render_topic_board, render_topic_host_rows, render_board_json` from `.render`
- [x] **Code**: rework the `board` callback per the traced algorithm — the mutual-exclusion clean error first (naming `--json` and `--info`), the two collection branches, the aggregate projection of the default view, the renderer dispatch (`shutil.get_terminal_size().columns` measured only for tables), `render_board_json(entries if not per_host else records)` for the JSON form, `ctx.exit(0)`; add the three options to the decorator stack (`--host` with `multiple=True` and the documented help; `--per-host`; `--json` bound to `json_output`); rewrite the callback docstring to the two views + JSON contract (the `--help` text, verbatim-rendered, no Args/Returns/Raises)
- [x] **Code**: update the `topics.py` module docstring's board paragraph to the two views and the JSON form
- [x] **Interface verification**: `python -m pytest tests/commands/topics/test_topics.py -k "Contract or board_carries" -x`
- [x] **Logic tests** (positive): `test_board_cli_default_view_collects_then_aggregates` — `CliRunner`; in the command module's import scope `collect_topic_board` mocked to return `[_record(...)]` and `aggregate_topic_board` mocked to return `[_entry(...)]`; `render_topic_board` mocked; `COLUMNS` pinned; `runner.invoke(topics, ["board"])` → `collect_topic_board.assert_called_once_with(None, False)`; `aggregate_topic_board.assert_called_once_with(records, ())` (click's absent `multiple=True` option delivers the empty tuple, which the domain reads as no filter); `render_topic_board.assert_called_once()`; exit code 0
- [x] **Logic tests** (positive): `test_board_cli_default_view_passes_host_to_aggregate_only` — as above with `--host feat/a --host main`; `runner.invoke(topics, ["board", "--host", "feat/a", "--host", "main"])` → `collect_topic_board.assert_called_once_with(None, False)` (no hosts kwarg); `aggregate_topic_board.assert_called_once_with(records, ("feat/a", "main"))`
- [x] **Logic tests** (positive): `test_board_cli_per_host_view_filters_collection` — `collect_topic_board`, `render_topic_host_rows`, `aggregate_topic_board` mocked in the command module scope; `runner.invoke(topics, ["board", "--per-host", "--host", "feat/a"])` → `collect_topic_board.assert_called_once_with(None, False, hosts=("feat/a",))` (the record filter travels as the keyword argument); `render_topic_host_rows` called with the records; `aggregate_topic_board` not called
- [x] **Logic tests** (positive): `test_board_cli_json_prints_aggregated_entries` — collectors mocked; `aggregate_topic_board` returns one `BoardEntry("feat-a", "feat/a", ["feat/a", "main"], ["planned"], True, False, "Fix.")`; `runner.invoke(topics, ["board", "--json"])` → `json.loads(result.output) == [{"topic": "feat-a", "branch": "feat/a", "hosts": ["feat/a", "main"], "statuses": ["planned"], "current": True, "remote": False, "todo": "Fix."}]`; `result.output.startswith("[\n    {")` (indent=4 pretty-printing); exit code 0
- [x] **Logic tests** (positive): `test_board_cli_json_per_host_records_have_no_hosts_key` — `collect_topic_board` mocked to return one `BoardRecord`; `runner.invoke(topics, ["board", "--per-host", "--json"])` → `set(json.loads(result.output)[0]) == {"topic", "branch", "statuses", "current", "remote", "todo"}`
- [x] **Logic tests** (positive): `test_board_cli_json_empty_board_prints_empty_array` — both collectors mocked to return `[]`; `runner.invoke(topics, ["board", "--json"])` → `result.output == "[]\n"`; exit code 0
- [x] **Logic tests** (negative): `test_board_cli_json_with_info_is_clean_error` — collectors mocked (must not be called); `runner.invoke(topics, ["board", "--json", "--info"])` → exit code 1; the error names both flags; `collect_topic_board` not called
- [x] **Logic tests** (edge): `test_board_cli_empty_board_table_prints_nothing` — both collectors mocked to return `[]`; `runner.invoke(topics, ["board"])` and `[..."--per-host"]` → `result.output == ""`; exit code 0
- [x] **Logic tests** (existing-test updates, expectation updates not deletions): `test_board_collects_and_renders_the_board` and `test_topics_board_info_flag_reaches_renderer` / `test_topics_board_info_short_form_binds_the_same_table` — mock `aggregate_topic_board` beside `collect_topic_board` (returning the `BoardEntry` mirror of the fixture record: topic/branch/statuses/current/remote/todo carried over, hosts `["feat/a"]`), keep the output assertions (the table now renders from the entry); `test_board_passes_the_year_and_the_remote_flag` and `test_board_short_forms_bind_the_same_values` — mock `aggregate_topic_board` (return `[]`), the `collect` call-shape assertions are unchanged; `test_board_measures_the_terminal_width` — the parametrization becomes `(40, 44)` and `(30, 44)` (the default grid is four columns now — the all-min-8 layout is 8·4 + 3·4 = 44 wide at both COLUMNS 40 and 30); re-run `test_board_domain_error_surfaces_clean` unchanged (the collect-side error propagates before the aggregate)
- [x] **Debugging**: `python -m pytest tests/commands/topics/test_topics.py -x` — fix implementation code until all tests pass (do NOT fix test code; do not weaken assertions)
- [x] **Contract re-verification**: the `board` method surface matches the manifest (signature, option surface, the six algorithm steps, the requirements — read-only, the year/remote scoping applied to the JSON exactly as to the table — and the constraints — no year/artifacts/heading outside the table or the array, no board computation at this layer)
- [x] **Lint**: `ruff check goga/commands/topics/topics.py` — fix formatting, apply decomposition if necessary

### Task 7: `topics.py` — the `create` subcommand and the optional-value `--todo` mapping (TDD coding)

This task implements the changed `create` method of the `topics` group
(`location: topics.py`): the three states of the optional-value `--todo`
option mapped into the domain declaration. Target file:
`goga/commands/topics/topics.py`; tests:
`tests/commands/topics/test_topics.py`. The mapping (from the design —
transfer):

```
1. existing guards: --commit without --publish; --switch with --publish
2. todo mapping (in the callback):
   IF todo == _TODO_DECLARED: todo = None; todo_from_stdin = True
   ELIF todo == "": todo = None                 # absent option
   ELSE: pass                                   # a real value or None
3. base and template resolution (unchanged, lazy _topics_section())
4. line = create_topic(branch_name, base, todo, todo_from_stdin,
   publish, template, scope.year, switch)
5. echo the line; ctx.exit(0)
```

`_TODO_DECLARED = "__declared__"` — a module-level constant reserved by
the command (the `click` practice's reserved-sentinel rule). The option
decorator becomes `is_flag=False, flag_value=_TODO_DECLARED, default=None`
(verified on click 8.5.0: absent → `None`, bare `--todo` → the sentinel,
`--todo TEXT` → the text, empty → `""`). Constraints: no editor, no stdin
read at this layer — the entry and the stdin channel belong to the domain.
The help docstring must be rewritten: the old "a value-less --todo is
click's own usage error" wording is now false — document the three states,
the UTF-8 rule, and the never-ignored piped content.

**Usages relevant to this task:**
- `click` (from Usages): the optional-value option pattern —
  `@click.option("--todo", "-t", "todo", is_flag=False,
  flag_value=_TODO_DECLARED, default=None)` with the three-state mapping
  in the callback and the reserved-sentinel rule; the existing guards and
  exit-code propagation.
- `creating` (from Imports): the creation contract with the acquisition
  ladder — shapes the mapping and the help text.
- `publishing` (from Imports): the publication contract behind
  `--publish` — an unchanged path behind the mapping.
- `registering-hooks` (from Imports): the lifecycle events the group's
  commands emit — the stdin todo passes through the same
  `amend_creation` checkpoint of the domain.
- The sibling `switch` and `delete` callbacks keep their paths — the
  `switching`, `deleting`, and `todo-entry` practices — untouched by
  this task.
- `project-configuration` (from Imports) + `checkpoints`: the unchanged
  lazy base/template resolution through `_topics_section()`.
- `convention`: the CLI docstring rule; `CliRunner` tests with
  `create_topic` mocked in the command module scope; a `tmp_path` cwd
  without a config file.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: update the existing `test_create_callback_signature` — the parameter list grows with `todo_from_stdin` directly after `todo` (`["scope", "branch_name", "todo", "todo_from_stdin", "publish", "base_ref", "from_current", "commit_message", "switch"]`, default `False`); rewrite `test_create_todo_option_surface` — its assertions hold on click 8.5.0 (`is_flag=False`, `flag_value` set, `default None`), but its docstring and the "no optional-value flag" comment must state the three-state surface and the reserved sentinel
- [x] **Code**: add the module-level constant `_TODO_DECLARED = "__declared__"`; change the `--todo` option to `is_flag=False, flag_value=_TODO_DECLARED, default=None` with updated help text (the three states)
- [x] **Code**: add the `todo_from_stdin` mapping in the callback (the traced step 2 — the sentinel → declaration, the empty string → absent, everything else passes) and pass `todo_from_stdin` positionally after `todo` in the `create_topic` delegation
- [x] **Code**: rewrite the `create` callback's help docstring per the design instruction — the three states of `--todo` (a value is the todo; the value-less form declares the piped stdin as the source; absent or empty declares nothing), the strict UTF-8 rule of the piped content, the never-silently-ignored piped content, the headless `--switch` creation now succeeding without a todo; keep the verbatim-rendered form (no Args/Returns/Raises)
- [x] **Code**: update the `topics.py` module docstring's creation paragraph (the optional-value todo option mapped into the domain's source declaration — no resolution at this layer)
- [x] **Interface verification**: `python -m pytest tests/commands/topics/test_topics.py -k "Contract or create" -x`
- [x] **Logic tests** (positive): `test_create_cli_todo_option_three_states` — `CliRunner`; `create_topic` mocked in the command module scope; a `tmp_path` cwd without a config file; base via `--from-current`; parametrized inputs `["create", "NAME", "--from-current", "-t", "Text."]`, `[..., "--todo", ...]`, `[...]` (no todo), and `[..., "-t", "", ...]` → the delegations `create_topic(..., "Text.", False, ...)`, `create_topic(..., None, True, ...)`, `create_topic(..., None, False, ...)`, `create_topic(..., None, False, ...)` (the `todo`, `todo_from_stdin` positionals)
- [x] **Logic tests** (positive): `test_create_cli_bare_todo_pipes_stdin_into_domain` — as above with `input=b"First\nSecond\n"` on the runner; `runner.invoke(topics, ["create", "Feature/Foo", "--todo", "--from-current"], input=b"First\nSecond\n")` → `create_topic` called with `todo=None, todo_from_stdin=True`; exit 0 (the real stdin ladder is covered by the domain tests)
- [x] **Logic tests** (existing-test updates, expectation updates not deletions): update every `create_topic.assert_called_once_with(...)` across the CLI test classes (~12 sites — `TestTopicsCreateAndSwitch`, `TestTopicsCreateBaseResolution`): the `todo_from_stdin` positional (`False` unless declared) slots in directly after `todo`; replace `test_create_bare_todo_flag_is_usage_error` — the value-less `--todo` is now a valid declaration (exit 0, delegation `todo=None, todo_from_stdin=True`), so the test becomes the declaration-path assertion (it may merge with `test_create_cli_bare_todo_pipes_stdin_into_domain`); keep `test_create_flag_with_value_passes_todo` and `test_create_empty_todo_value_counts_as_absent` passing (their traced outcomes are unchanged by the mapping)
- [x] **Debugging**: `python -m pytest tests/commands/topics/test_topics.py -x` — fix implementation code until all tests pass (do NOT fix test code; do not weaken assertions)
- [x] **Contract re-verification**: the `create` method surface matches the manifest (signature with `todo_from_stdin`, the eight algorithm steps — the guards first, the mapping before the delegation, the unchanged base/template resolution — and the constraints: no editor, no stdin read, no branch switching or board rendering at this layer)
- [x] **Lint**: `ruff check goga/commands/topics/topics.py` — fix formatting, apply decomposition if necessary

### Task 8: `goga/commands/topics` facade — export the two new renderers (infrastructure)

This task completes the facade obligation of the `goga/commands/topics`
cell: `render_topic_host_rows` and `render_board_json` must be importable
from the package root beside `render_topic_board`, with `__all__` growing
to four names. Target file: `goga/commands/topics/__init__.py`; tests:
`tests/commands/topics/test_topics.py` (the facade contract test).

**Usages relevant to this task:**
- `convention`: the facade is `__init__.py` with `__all__`; alphabetical
  order; the module docstring is a contract mirror.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Extend the render import in `goga/commands/topics/__init__.py` to `from .render import render_board_json, render_topic_board, render_topic_host_rows`
- [x] Grow `__all__` to the four alphabetical names: `["render_board_json", "render_topic_board", "render_topic_host_rows", "topics"]`
- [x] Update the module docstring to the new contract (the board rendered in its two views and its JSON form; the optional-value todo option mapped into the domain's source declaration) — a contract mirror, not narration
- [x] Update the existing facade contract test `test_facade_exports_two_names` in `tests/topics`'s sibling `tests/commands/topics/test_topics.py` — rename it to state the four names and assert `_topics_facade.__all__ == ["render_board_json", "render_topic_board", "render_topic_host_rows", "topics"]` with each name importable (the `_topics_facade` resolver already exists in the file); extend the render contract test's facade-identity assertions to the two new names
- [x] Verify facade accessibility: `python -c "from goga.commands.topics import render_topic_board, render_topic_host_rows, render_board_json, topics"` and `python -m pytest tests/commands/topics -k "facade or Facade" -x`
- [x] Lint: `ruff check goga/commands/topics/__init__.py` — fix formatting if necessary

### Task 9: Integration tests — the CLI board flow over the wired domain (integration tests)

This task verifies the cross-cell flow end-to-end: the `topics.board`
callback (real) → the domain board pipeline (real `collect_topic_board` +
real `aggregate_topic_board` over the git boundary mocked at the import
points in `goga.topics.board`) → the real renderers — through `CliRunner`.
The patching works across the cell boundary because the CLI imports the
facade function whose internals resolve the module-level names in
`goga.topics.board`. Tests are added to
`tests/commands/topics/test_topics.py` (a new `TestTopicsBoardFlow`
class). Pin `COLUMNS=100` (caps 22 per column at k=4; every line ≤ 100).

**Usages relevant to this task:**
- `convention`: the mock-at-import-point discipline (`_wire_board`
  pattern), the built-in scale pinned by a local `_builtin_scale()`
  helper mirroring `tests/topics/conftest.py`'s `builtin_scale` fixture
  (the fixture is scoped to `tests/topics/` — the precedent is
  `tests/commands/pipeline/test_pipeline_dispatch.py`; patch
  `goga.topics.board.assemble_status_scale`, `list_branch_refs`,
  `resolve_current_branch_name`, `read_ref_tree_paths`,
  `read_ref_file`), `tmp_path` + `monkeypatch.chdir` with the real
  history path routines.
- `click`: `CliRunner`, the pinned `COLUMNS` environment.
- `topic-board`: the two projections this flow renders.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Add the `TestTopicsBoardFlow` class to `tests/commands/topics/test_topics.py` with a local `_wire_domain_board` helper patching the five import points in `goga.topics.board` (mirror `tests/topics/test_board.py`'s `_wire_board`) over the base scenario: inventory `feat/a` (local), `origin/feat/a`, `origin/feat/b` (remote), `main` (local); trees hosting feat-a plan.md on `feat/a` and its twin, feat-b prd.md on `origin/feat/b`; current `feat/a`; the working-copy topic `.goga/history/2026/feat-a/plan.md` created under `tmp_path` with `monkeypatch.chdir`
- [ ] Test cross-entity interaction: the default view — `runner.invoke(topics, ["board"])` → exit 0; the header is the four-column `| Topic | Branch | hosts | Statuses |`; the `* feat-a` current marker appears; the remote own branch `origin/feat/b` stays visible in the branch column; the statuses `[defined]` and `[planned]` appear; every output line ≤ 100 columns
- [ ] Test cross-entity interaction: the per-host view — `runner.invoke(topics, ["board", "--per-host"])` → exit 0; the header is the three-column `| Topic | Branch | Statuses |`; one row per record (the twin-collapsed pair)
- [ ] Test cross-entity interaction: the JSON view — `runner.invoke(topics, ["board", "--json"])` → exit 0; `json.loads(result.output)` yields two objects, each with the `hosts` key (feat-a: `["feat/a"]`; feat-b: `["origin/feat/b"]`); the output starts with `"[\n    {"`
- [ ] Test edge case: the host filter through the whole stack — `runner.invoke(topics, ["board", "--host", "feat/a"])` → only the feat-a entry renders; `runner.invoke(topics, ["board", "--host", "no-such-branch"])` → empty output, exit 0 (a filter, never an error)
- [ ] Run validation: `python -m pytest tests/commands/topics/test_topics.py -x`

---

## Validation Commands

- `python -m pytest tests/topics tests/commands/topics -x`: Run all tests of both touched packages (the design's gate: `pytest tests/topics tests/commands/topics -x`)
- `ruff check goga/`: Lint check (the design's gate)
- `python -c "from goga.topics import BoardEntry, aggregate_topic_board"`: Verify the `goga/topics` facade exports (the design's gate)
- `python -c "from goga.commands.topics import render_topic_board, render_topic_host_rows, render_board_json, topics"`: Verify the `goga/commands/topics` facade exports
- `goga lint`: Contract lint — 0 errors expected (80 cells)

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location` (`board.py`, `creation.py`, `render.py`, `topics.py`)
- [ ] Every contract entity is accessible from the facade (`BoardEntry`, `aggregate_topic_board` on `goga/topics`; the three renderers + `topics` on `goga/commands/topics`)
- [ ] Properties and methods match the declared API (`hosts` on `collect_topic_board`; `todo_from_stdin` on `create_topic` and `topics.create`; `host`/`per_host`/`json_output` on `topics.board`; `entries: list[BoardEntry]` on `render_topic_board`)
- [ ] Descriptions are reflected in behavior (the two projections, the ladder, the ask skip, the width fractions, the JSON shapes, the filter semantics)
- [ ] Contract dependencies are met (`BoardEntry` imported from `...topics` in `render.py`; `aggregate_topic_board` imported in `topics.py`)
- [ ] Re-exports are accessible from the facade (the four-name and two-new-name `__all__` extensions)
- [ ] Every coding task followed the TDD workflow (contract tests → code → verification → logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding task
- [ ] Integration tests exist where cross-entity scenarios require them (Task 4: collect → aggregate; Task 9: CLI → domain → renderers)
- [ ] No package boundary was expanded (no new cells, no new interfaces beyond the manifests)
- [ ] `CODEMANIFEST` files were not modified (contract is read-only); no `.usages/` file was modified (all current per the design)
- [ ] All validation commands pass
- [ ] Every Usages entry is mentioned in at least one task (`convention`, `click`, `beautiful_json`, and the imported `topic-board`, `creating`, `editor-entry`, `topic-paths`, `topic-statuses`, `refs-and-switching`, `publishing`, `deleting`, `switching`, `todo-entry`, `project-configuration`, `checkpoints`, `registering-hooks`)
