# Design Document: `topic-influence`

The architectural specification of the topic-influence feature: the two board
projections (the per-host audit records as the single source of facts, the
aggregated one-entry-per-topic default view), the host filter, the JSON board
output, and the todo acquisition ladder of the creation (value → declared
stdin → editor → clean error) with the optional-value `--todo` option.

Derived from the CODEMANIFEST changes of `goga/topics` and
`goga/commands/topics` materialized by the apply stage from
`.goga/history/2026/topic-influence/arch.md`.

---

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/topics/CODEMANIFEST`: the inventory contract split into two
  projections — `collect_topic_board` gains the `hosts` record filter and
  the audit-view wording; new `BoardEntry` entity and new
  `aggregate_topic_board` routine (both `location: board.py`);
  `create_topic` gains `todo_from_stdin` and the acquisition ladder; the
  global annotations, the `BoardRecord` wording, and the footer description
  describe the two views and the stdin channel.
- `goga/commands/topics/CODEMANIFEST`: Imports gain `BoardEntry` and
  `aggregate_topic_board` from `goga/topics`; Usages gain `beautiful_json`;
  the `topics` group's `board` method gains `host`, `per_host`,
  `json_output` (repeatable `--host`, `--per-host`, `--json`); the `create`
  method gains `todo_from_stdin` (the optional-value `--todo` mapping);
  `render_topic_board` retargets to `list[BoardEntry]` with the hosts
  column; new `render_topic_host_rows` (the former per-record table) and
  new `render_board_json` (all `location: render.py`).

### New Entities

- `BoardEntry(topic, branch, hosts, statuses, current, remote, todo=None)` —
  one entry of the default board: a topic that still has its own branch,
  with every branch carrying its history. `goga/topics/board.py`.
- `aggregate_topic_board(records, hosts=None)` — routine projecting the
  per-host records into the default board. `goga/topics/board.py`.
- `render_topic_host_rows(records, width, info=False)` — routine rendering
  the per-host audit table. `goga/commands/topics/render.py`.
- `render_board_json(board)` — routine rendering either view as a
  pretty-printed JSON array. `goga/commands/topics/render.py`.

### Changed Entities

- `collect_topic_board(year, remote, hosts=None)` — gains the `hosts`
  record filter (exact display-name equality, union; unknown → empty
  list); wording re-targeted to the audit view as the source of facts.
- `create_topic(branch_name, base_ref, todo, todo_from_stdin, publish,
  commit_message, year, switch)` — the todo resolves through the
  acquisition ladder; the publication ask skips itself when the todo came
  from stdin.
- `topics.board(remote, info, host, per_host, json_output)` — two table
  views and the JSON form; the `--json`+`--info` combination is a clean
  error.
- `topics.create(...)` — maps the three states of the optional-value
  `--todo` option into `todo` / `todo_from_stdin`.
- `render_topic_board(entries, width, info=False)` — takes
  `list[BoardEntry]`; four-column default grid (topic, branch, hosts,
  statuses), five-column under `info` (todo between hosts and statuses).

### Deleted Entities

- None.

### Usages and Annotations Changes

- `goga/commands/topics` Usages: `beautiful_json:
  .goga/usages/cooks/beautiful_json.md` connected; referenced in the
  global annotations, the `board` method annotation, and
  `render_board_json`.
- `.goga/usages/cooks/click.md`: new section "Option — optional value
  (three states)" with the reserved-sentinel bullet (applied by the
  apply stage).
- Cell-level `.usages` updated by the apply stage: `goga/topics/.usages/
  topic-board.md` (two projections), `goga/topics/.usages/creating.md`
  (ladder + stdin rules), `goga/commands/topics/.usages/
  topics-command.md` (board views, JSON, optional-value todo).

## Applied Fixes

### Fixed CODEMANIFEST Defects

- `goga/commands/topics/CODEMANIFEST`, `render_topic_board` Requirements:
  the width-rule fractions were each off by one column after the hosts
  column was added (defect type: interface ↔ interface inconsistency —
  the fractions contradict the same bullet's minimum-8 rule, the
  "table never exceeds `width`" invariant, and the sibling wording of
  `render_topic_host_rows`):
  - Four-column rule: "capped at one third of `width` minus the dividers"
    → "one quarter" (at `width=100`: literal thirds give statuses 1
    column, forcing the min-8 floor and a 107-column table).
  - Five-column rule under `info`: "each capped at one quarter" →
    "one fifth".
  - Approved by the user; `goga lint` re-run clean (80 cells, 0 errors).
  - The equal-share formula everywhere: `usable = width − 3·k`,
    every column capped at `usable // k`, statuses receives the
    remainder; the named fraction is always `1/k` of `usable`. Narrow
    thresholds: 44 for the four-column grid, 55 for the five-column
    grid, 33/44 for the host-rows grids.

## Entity Interaction and Data Flow

### Interaction Diagram

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

### Data Flows

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

### Entity Dependencies

- `aggregate_topic_board` depends on `BoardRecord` and `BoardEntry`
  (same module) and on `normalize_topic_slug` + `assemble_status_scale`
  from `goga/history` (already imported in `board.py`;
  `assemble_status_scale` is already imported for the collection).
- `render_topic_board` / `render_board_json` depend on `BoardEntry`
  (new import in `render.py`); `render_topic_host_rows` keeps
  `BoardRecord`.
- `topics.board` depends on both collectors and all three renderers.
- `topics.create` depends on the extended `create_topic` signature.
- Initialization order (design order): `board.py` entities first (the
  domain is the leaf of the CLI), then the `goga/topics` facade (the
  `BoardEntry` export `render.py` imports), then `render.py`, then
  `topics.py`, then the `goga/commands/topics` facade.

## Code Stack Trace

### Trace: `collect_topic_board(year, remote, hosts)`

#### Chain

1. **Input**: CLI board (both views) or a consumer; `year: str | None`,
   `remote: bool`, `hosts: tuple[str, ...] | None`.
2. Public wrapper catches `subprocess.CalledProcessError`,
   `FileNotFoundError`, `ImportError` → `click.ClickException` (unchanged
   cell boundary) → checkpoint: unchanged, passes.
3. `_board_records(year, remote)`: `resolved_year = year or
   current_year()`; `scale = assemble_status_scale()`; `inventory =
   list_branch_refs()`; `current = resolve_current_branch_name()`; `refs`
   = remote-tracking only in remote mode, full inventory otherwise →
   checkpoint: types match the history/git facades, passes.
4. `_year_topics_by_ref` → one `read_ref_tree_paths(ref, prefix)` per ref
   under `resolve_history_root().as_posix() + "/"`; `_year_topics` splits
   `.goga/history/<year>/<slug>/<artifact…>` (`parts[2] == year`) →
   checkpoint: prefix carries the trailing slash (posix), passes.
5. Per-ref rows keyed `(slug, ref.name)` with `(is_remote,
   scale.maximal_present(artifacts), _todo_summary(read_ref_file(...)))`;
   the current branch's row reads the working copy via
   `_current_branch_topic` → checkpoint: `resolve_topic_status` /
   `StatusScale.maximal_present` signatures verified, passes.
6. `_collapse_remote_twins` — a remote row whose short name matches a
   local key of the same slug drops; `_marks_current` sets the current
   flag (short-name comparison in remote mode) → checkpoint: passes.
7. **New** — the `hosts` record filter, applied to the built records
   before the sort: `if hosts: names = set(hosts); records = [r for r in
   records if r.branch in names]` → checkpoint: `r.branch` is the display
   name the contract filters on; `None` and `()` both skip the filter;
   unknown names yield `[]` (a filter, never an error) — passes.
8. Sort by `(scale_order[statuses[0]], topic)`; return → checkpoint: a
   record always has at least `["empty"]` (the scale floor), so
   `statuses[0]` is never an index error — passes.
9. **Output**: `list[BoardRecord]`, one per topic and hosting branch,
   sorted; consumed by `aggregate_topic_board`,
   `render_topic_host_rows`, `render_board_json`.

#### Checkpoint Summary

- Type flow into `aggregate_topic_board` / renderers: `list[BoardRecord]`
  with the six declared fields — passed.
- Filter position (after collapse, before sort) matches contract steps
  9–10 — passed.
- No contract defect found.

### Trace: `aggregate_topic_board(records, hosts)`

#### Chain

1. **Input**: the collected `records: list[BoardRecord]` (already
   sorted), `hosts: tuple[str, ...] | None`.
2. Public wrapper (new, mirrors `collect_topic_board`): catches
   `ImportError` of the internal scale assembly → `click.ClickException`;
   no git boundary handlers needed (no git access) → checkpoint: the
   cell's "fatal scale-assembly ImportError surfaces as
   click.ClickException" annotation holds — passes.
3. Grouping: `groups: dict[str, list[BoardRecord]]` in first-encounter
   order (input order preserved; the input list itself is never touched)
   → checkpoint: read-only requirement — passes.
4. Hosts list per topic: take each record's `branch`; drop a remote
   record whose short name (`partition("/")[2]`) equals the display name
   of a non-remote record of the same group (the twin counts once, under
   the local name); `sorted(set(...))` alphabetical → checkpoint: matches
   contract step 2 — passes.
5. Own-branch candidates: records whose branch part —
   `record.branch` whole when not `record.remote`, `partition("/")[2]`
   when `record.remote` — satisfies `normalize_topic_slug(branch_part) ==
   topic` → checkpoint: `normalize_topic_slug` already imported in
   `board.py`; "release/1.3.0" → "release-1-3-0" and
   "origin/release/1.3.0" → short "release/1.3.0" → same slug — passes.
6. Winner among candidates, deterministic key `(not current, remote,
   branch)` → `min(...)`; a group without candidates produces no entry →
   checkpoint: matches contract step 4 (current → non-remote → alphabet)
   — passes.
7. `BoardEntry(topic=slug, branch=winner.branch, hosts=hosts_list,
   statuses=winner.statuses, current=any(r.current for r in group),
   remote=winner.remote, todo=winner.todo)` → checkpoint: constructor
   fields match the declared signature — passes.
8. Sort: `scale_order = {stage.name: i for i, stage in
   enumerate(assemble_status_scale().stages)}` (assembled once here, the
   sort axis only — see Algorithm Design for the rationale); entries sort
   by `(scale_order[statuses[0]], topic)` → checkpoint: the winner's
   `statuses[0]` is a scale member because the records were built by the
   same scale family; assembly is not git access and violates no
   requirement — passed (documented decision, not a defect).
9. `hosts` filter: `if hosts: names = set(hosts); entries = [e for e in
   entries if any(h in names for h in e.hosts)]` → checkpoint:
   membership in the hosts list (not display-name equality — that is the
   record filter); never resurrects a topic without an own branch
   (filter runs after the own-branch gate) — passes.
10. **Output**: `list[BoardEntry]`, sorted; consumed by
    `render_topic_board`, `render_board_json`.

#### Checkpoint Summary

- `BoardRecord` fields ↔ `BoardEntry` fields: statuses/remote/todo from
  the winner, current from the group — passed.
- Empty `records` → `[]`; unknown `hosts` name → `[]` — passed.
- No contract defect found.

### Trace: `create_topic(..., todo_from_stdin, ...)` (the ladder)

#### Chain

1. **Input**: CLI create (mapped states) or a consumer;
   `todo: str | None`, `todo_from_stdin: bool`.
2. Public wrapper: the existing handlers unchanged; the new
   `UnicodeDecodeError` of the stdin decode is converted to
   `click.ClickException` at the decode site inside the ladder (it is a
   `ValueError` subclass and would otherwise pierce the boundary) →
   checkpoint: the clean-error boundary stays closed — passes.
3. `_create_topic` preflight (unchanged): slug guard, current-branch
   conflict, `check_branch_occupancy` → `check_slug_occupancy`,
   `resolve_ref_commit` → checkpoint: the stdin read happens after the
   preflight per the requirement — passes.
4. `_resolve_todo(todo, todo_from_stdin) -> tuple[str | None, bool]`
   (replaces the old `_resolve_todo`; returns the todo and the
   came-from-stdin fact):
   - a. `if todo:` → `(todo, False)`; stdin never touched → checkpoint:
     "an explicit value wins over piped content" — passes.
   - b. `elif not sys.stdin.isatty():` → `data =
     sys.stdin.buffer.read()` (exactly once); `content =
     data.decode("utf-8")` with a `try` converting
     `UnicodeDecodeError` → `click.ClickException` naming the todo
     option; `has_content = bool(content.strip())` (whitespace-only
     decides, the content itself is never trimmed); then the four cases:
     declared+content → `(content, True)`; declared+bare → editor
     rung; undeclared+content → `click.ClickException` naming the todo
     option; undeclared+bare → editor rung → checkpoint: matches
     contract rung b verbatim — passes.
   - c/d. editor rung: `edit_text()` when `sys.stdin.isatty()` else
     `None` → checkpoint: a TTY stdin is never read (the read sits
     behind the `not isatty()` branch); a non-interactive terminal
     leaves no todo (the old unconditional clean error is gone — rung e
     decides) — passes.
5. Rung e — path rules (moved after the ladder, replacing the old
   pre-ask guards): `publish` and todo None → clean error asking for
   the todo; `not publish and not switch` and todo None → the local
   todo error (message names the todo sources and the switch form);
   `switch` tolerates None → checkpoint: contract requirement "every
   decision precedes the first mutation" — all three are pre-mutation —
   passes.
6. Publication ask: `_publication_asked(publish, todo, came_from_stdin)`
   — asks only when `not publish and todo is not None and
   came_from_stdin is False and sys.stdin.isatty()` → checkpoint: the
   stdin-sourced todo never triggers the ask — passes.
7. Amendment (unchanged shape): `TopicHooks().amend_creation(identity,
   checked_out=..., published=..., commit_message=draft_message,
   todo=resolved_todo)` — the stdin todo flows through the same
   amendment as a value or an editor text → checkpoint: "every todo
   source passes through the same amendment hooks" — passes.
8. Mutation paths (unchanged mechanics): no-switch plant / switch path /
   publication delegation; the stdin-resolved todo is written with the
   value-form semantics (`_write_todo` adds the single trailing
   newline, UTF-8) → checkpoint: verbatim content + write-time
   normalization only — passes.
9. **Output**: the single result line.

#### Checkpoint Summary

- The four stdin cases and the TTY guard trace clean — passed.
- The ladder reuses `_write_todo` and the amendment unchanged — the
  stdin source carries value-form semantics — passed.
- No contract defect found.

### Trace: `topics.board(remote, info, host, per_host, json_output)`

#### Chain

1. **Input**: click parses `--remote/-r`, `--info/-i`, repeatable
   `--host` (`multiple=True`; absent yields `()`, which the domain reads
   as no filter), `--per-host`, `--json` (Python name `json_output`).
2. `json_output and info` → `click.ClickException` (before any git
   access) → checkpoint: algorithm step 1 order — passes.
3. Default view: `records = collect_topic_board(scope.year, remote)`;
   `entries = aggregate_topic_board(records, host)` → checkpoint: the
   full inventory is collected (no record filter) because hosts lists
   need every hosting branch — matches the contract algorithm — passes.
4. Per-host view: `records = collect_topic_board(scope.year, remote,
   hosts=host)` → checkpoint: record filter semantics — passes.
5. Table: `width = shutil.get_terminal_size().columns`; default →
   `render_topic_board(entries, width, info)`; per-host →
   `render_topic_host_rows(records, width, info)` → checkpoint: both
   renderers print nothing on empty input — passes.
6. JSON: `render_board_json(entries if not per_host else records)` →
   checkpoint: `[]` prints `[]` — passes.
7. `ctx.exit(0)`; empty board included → checkpoint: exit codes —
   passes.
8. **Output**: the table or the JSON array on stdout; exit 0.

#### Checkpoint Summary

- Option surfaces match the `click` practice (repeatable option tuple
  semantics; empty tuple ≠ None check) — passed.
- No git/editor/stdin access at this layer — passed.
- No contract defect found.

### Trace: `topics.create(...)` (the option mapping)

#### Chain

1. **Input**: click parses `--todo/-t` as the optional-value option —
   `is_flag=False, flag_value=_TODO_DECLARED, default=None` where
   `_TODO_DECLARED = "__declared__"` (module-level reserved sentinel per
   the `click` practice; verified on click 8.5.0: absent → `None`,
   bare `--todo` → the sentinel, `--todo TEXT` → the text).
2. Existing pre-delegation guards unchanged (`--commit` without
   `--publish`; `--switch` with `--publish`).
3. The mapping (algorithm step 5, in the callback): `todo` is a non-empty
   real value → the todo; `todo == _TODO_DECLARED` → `todo = None`,
   `todo_from_stdin = True`; `todo is None or todo == ""` → nothing →
   checkpoint: an empty real value counts as absent (kept from the old
   surface); the sentinel is reserved — a real value equal to it is
   indistinguishable from the declaration (documented practice) —
   passes.
4. Base and template resolution unchanged (`_topics_section()` lazily,
   `--base-ref` → `topics.base_ref` → `--from-current` HEAD; the
   `ConfigHooks` checkpoint inside the load).
5. Delegation: `create_topic(branch_name, base, todo, todo_from_stdin,
   publish, template, scope.year, switch)` — positional order matches
   the domain signature → checkpoint: type flow `bool` into
   `todo_from_stdin` — passes.
6. Echo the result line; propagate the exit code.
7. **Output**: one line on stdout; exit code.

#### Checkpoint Summary

- No editor, no stdin read at this layer (the constraint) — passed.
- Docstring (`--help` text) must be rewritten: the old "a value-less
  --todo is click's own usage error" wording is now false — recorded as
  an implementation instruction — passed (documentation, not a contract
  defect).

### Trace: `render_topic_board(entries, width, info)`

#### Chain

1. **Input**: `entries: list[BoardEntry]` (already sorted by the domain),
   `width: int`, `info: bool`.
2. Empty → return (prints nothing) → checkpoint: passes.
3. `columns_count = 5 if info else 4`; `caps = _column_widths(width,
   columns_count)` — the existing helper already computes the corrected
   equal-share rule (`usable = width − 3·k`, cap `usable // k`, statuses
   the remainder; all-min-8 below `k·8 + 3·k`) → checkpoint: with the
   fixed fractions ("one quarter" / "one fifth") the helper satisfies
   every width requirement verbatim — passed (this trace is what
  exposed the D1 defect; fixed and approved).
4. Header `(Topic, Branch, hosts, Statuses)` / `(Topic, Branch, hosts,
   todo, Statuses)`; one separator row → checkpoint: "the hosts column
   header is the word hosts" — passes.
5. Per entry: `topic_text = "* " + topic` when `entry.current`; the
   hosts column content — the entry's `hosts` names wrapped whole onto
   continuation lines through the same greedy filler as statuses
   (`_wrap_segments(entry.hosts, hosts_cap)` — plain names, no
   brackets); the statuses column `[name]` segments wrapped as today;
   the row line count is `max(len(host_lines), len(status_lines), 1)`;
   continuation lines carry the earlier columns empty → checkpoint: the
   hosts and the statuses wrap without affecting the column widths; an
   overlong host name truncates with the ellipsis inside the filler —
   passes.
6. A row divider closes every record, the last included → checkpoint:
   existing behavior kept — passes.
7. `todo` of None/empty renders an empty cell; the remote prefix of a
   remote own branch stays visible in the branch column (the branch
   prints as stored) → checkpoint: passes.
8. **Output**: the grid on stdout via `click.echo`.

#### Checkpoint Summary

- `BoardEntry` fields ↔ rendering references — passed.
- Width arithmetic ↔ requirements (post-fix) — passed.

### Trace: `render_topic_host_rows(records, width, info)`

#### Chain

1. **Input**: `records: list[BoardRecord]`, `width`, `info`.
2. The current `render_topic_board` body moves here unchanged in
   mechanics: `columns_count = 4 if info else 3`; three-column /
   four-column rules ("one third" / "one quarter" — already correct);
   header `(Topic, Branch, Statuses)` / `(Topic, Branch, todo,
   Statuses)`; per-record rows with wrapped statuses; row dividers;
   current marker; empty → nothing.
3. **Output**: the audit grid on stdout.
4. → checkpoint: pure rename + docstring retitle; the existing tests of
   the old `render_topic_board` transfer here — passed.

### Trace: `render_board_json(board)`

#### Chain

1. **Input**: `board: list[BoardEntry] | list[BoardRecord]` —
   homogeneous by construction (one view per call).
2. Per item, discriminate by `isinstance(item, BoardEntry)`: an entry →
   `{"topic", "branch", "hosts", "statuses", "current", "remote",
   "todo"}`; a record → the same without `hosts`; `todo` carries the
   summary string or `None` (never omitted) → checkpoint: the shapes are
   the declared stable consumer contract — passes.
3. `payload = json.dumps(items, indent=4, sort_keys=True,
   ensure_ascii=False)` — the `beautiful_json` practice verbatim;
   `click.echo(payload)` adds the one trailing newline → checkpoint:
   "echo it with one trailing newline" — passes.
4. Empty `board` → `items == []` → prints `[]` → checkpoint: passes.
5. **Output**: the JSON array on stdout; nothing else.

#### Checkpoint Summary

- `sort_keys=True` ↔ "the key order is not part of [the contract]" —
  passed.
- No mutation of `board` — passed.

### Trace: the facades

- `goga/topics/__init__.py`: extend the `from .board import ...` line to
  `BoardEntry, BoardRecord, aggregate_topic_board, collect_topic_board`;
  add `"BoardEntry"` and `"aggregate_topic_board"` to `__all__`
  (alphabetical). → checkpoint: the imports referenced by
  `goga/commands/topics` (and by the plan's build checklist) resolve —
  passed.
- `goga/commands/topics/__init__.py`: export
  `render_topic_host_rows` and `render_board_json` beside
  `render_topic_board`; `__all__` grows to four names (alphabetical) →
  checkpoint: symmetric with the existing export style — passed.

## Algorithm Design

### `BoardEntry`

**Responsibility**: the data model of one default-board row.

**Algorithm** (construction only — a frozen `kw_only` dataclass per the
`convention` practice, mirroring `BoardRecord`):

```
1. dataclass(frozen=True, kw_only=True)
2. fields: topic: str, branch: str, hosts: list[str],
   statuses: list[str], current: bool, remote: bool,
   todo: str | None = None
```

**Errors**: none (a pure data holder).

**Edge Cases**: `hosts` may be a one-element list (a topic hosted only by
its own branch); `todo` None (no todo.md) or `""` (a todo.md whose every
line reduces to emptiness) — presence differs from absence, kept from
`BoardRecord`.

### `collect_topic_board` (changed)

**Responsibility**: the audit collection — one record per topic and
hosting branch; the single source of the board's facts.

**Algorithm**:

```
1. steps 1–8 unchanged (year, scale, inventory, ref trees, statuses,
   todo summaries, twin collapse, current marking)
   → list[BoardRecord] unfiltered
2. IF hosts is not None and hosts:
   - names = set(hosts)
   - records = [r for r in records if r.branch in names]   # exact
     display-name equality, union across values; unknown → []
3. sort by (scale_order[statuses[0]], topic); return
```

**Errors**: the unchanged cell boundary — git infrastructure failures
and the fatal scale-assembly `ImportError` → `click.ClickException`.

**Edge Cases**: `hosts=None` or `()` → no filter; an unknown name → the
empty list (never an error); the filter composes with `remote` mode
(display names are then remote-tracking names).

### `aggregate_topic_board`

**Responsibility**: the default-view projection — exactly one entry per
topic that still has its own branch.

**Algorithm**:

```
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
6. return entries
```

The internal scale assembly (step 1) is a deliberate design decision:
the entry sort key is the *winner's* first maximal status, which can
differ from the first record's (the input order follows the least
advanced host), so the input order alone cannot sort the entries. The
assembly is not git access and not a board fact; the cell's
clean-error boundary wraps its fatal `ImportError`. The platform
explicitly designs the assembly to run at every point that needs the
scale (never cached).

**Errors**: the fatal scale-assembly `ImportError` →
`click.ClickException` (the only handler of the wrapper).

**Edge Cases**: empty `records` → `[]`; a topic without an own branch →
no entry whatever hosts carry it (the own-branch gate precedes the
filter); several colliding own branches → the deterministic winner; a
remote-tracking own branch qualifies (`remote=True` on the entry).

### `create_topic` (changed — the acquisition ladder)

**Responsibility**: the fresh-work orchestration; the todo resolves
through value → declared stdin → editor → path rules.

**Algorithm** (the changed part; everything else keeps its traced shape):

```
_resolve_todo(todo, todo_from_stdin) -> (todo | None, came_from_stdin):
1. IF todo: RETURN (todo, False)            # stdin stays unread
2. IF not sys.stdin.isatty():
   a. data = sys.stdin.buffer.read()        # fully, exactly once
   b. TRY content = data.decode("utf-8")
      EXCEPT UnicodeDecodeError: clean error naming the todo option
   c. has_content = content.strip() != ""   # whitespace decides only
   d. IF todo_from_stdin and has_content:
        RETURN (content, True)              # verbatim; no editor, no ask
   e. IF not todo_from_stdin and has_content:
        clean error naming the todo option  # piped content is never
                                            # silently ignored
   f. fall through to the editor rung       # declared+bare, or
                                            # undeclared+bare
3. RETURN (edit_text() if sys.stdin.isatty() else None, False)

then, in _create_topic (rung e — the path rules, after the ladder):
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

**Errors**: the stdin decode failure converts to
`click.ClickException` at the decode site; the undeclared-content case
and the path rules raise clean errors; every pre-existing handler of
the wrapper is unchanged.

**Edge Cases**: a TTY stdin is never read; a non-TTY stdin without
content and without declaration leaves no todo (headless `switch`
creation succeeds without one — new capability; headless no-switch
creation hits the local-todo error); an explicit value wins over piped
content; `--publish` with a stdin todo publishes without the ask.

### `topics.board` (changed)

**Responsibility**: the CLI surface of both board views and the JSON
form.

**Algorithm**:

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

Option surfaces: `--remote/-r` and `--info/-i` flags (unchanged);
`--host` — `multiple=True`, no short form (collisions: `-h` is help),
`help` text documenting exact display-name match and the union;
`--per-host` — flag; `--json` — flag, Python name `json_output`.

**Errors**: clean errors only; domain errors already arrive as
`click.ClickException`.

**Edge Cases**: empty board → nothing as a table, `[]` as JSON, exit 0;
an unknown `--host` name → the empty board, never an error; `--host`
composes with `--remote`, `--per-host`, and `--json`.

### `topics.create` (changed — the option mapping)

**Responsibility**: mapping the three states of the optional-value
`--todo` into the domain declaration.

**Algorithm**:

```
1. existing guards: --commit without --publish; --switch with --publish
2. todo mapping:
   IF todo == _TODO_DECLARED: todo = None; todo_from_stdin = True
   ELIF todo == "": todo = None                 # absent option
   ELSE: pass                                   # a real value or None
3. base and template resolution (unchanged, lazy _topics_section())
4. line = create_topic(branch_name, base, todo, todo_from_stdin,
   publish, template, scope.year, switch)
5. echo the line; ctx.exit(0)
```

`_TODO_DECLARED = "__declared__"` — a module-level constant reserved by
the command (the `click` practice's reserved-sentinel rule).

**Errors**: unchanged clean errors.

**Edge Cases**: `--todo=""` counts as absent; a real value equal to the
sentinel is treated as the declaration (reserved).

### `render_topic_board` (changed)

**Responsibility**: the default-view table.

**Algorithm**:

```
1. IF not entries: return
2. k = 5 if info else 4; caps = _column_widths(width, k)
   # usable = width − 3k; text columns usable//k; statuses the remainder;
   # all columns 8 when usable < 8k
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
```

**Errors**: none (pure output).

**Edge Cases**: `todo` None/`""` → empty cell; overlong host or status
names truncate with the single ellipsis inside the wrap filler; the
current marker consumes topic-cap columns (existing behavior); the
table exceeds `width` only below the narrow threshold (44 / 55).

### `render_topic_host_rows`

**Responsibility**: the audit-view table — the established layout
preserved.

**Algorithm**: the current `render_topic_board` body verbatim with the
`k = 4 if info else 3` grids, `(Topic, Branch[, todo], Statuses)`
headers, wrapped statuses, row dividers, current marker; retitled
docstring for the audit view.

**Errors**: none.

**Edge Cases**: identical to today's board table.

### `render_board_json`

**Responsibility**: the machine-readable projection of either view.

**Algorithm**:

```
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

**Errors**: none.

**Edge Cases**: empty → `[]`; the todo key is `null` or a string,
never omitted.

## Cross-cutting Concerns

- **Error handling**: the cell's clean-error boundary
  (`click.ClickException`) extends to the two new surfaces — the
  `aggregate_topic_board` scale-assembly `ImportError` and the stdin
  UTF-8 decode failure (converted at the decode site, since
  `UnicodeDecodeError` is a `ValueError` the wrapper does not catch).
  The CLI maps `--json --info` to a clean error before any git access.
- **Logging**: nothing new — the domain logs nothing today; hooks-zone
  warnings stay in the hooks zone.
- **Validation**: the ladder's whitespace-only content test; the hosts
  filter's exact display-name equality (unknown names are empty
  results, not errors); the `--json`/`--info` mutual exclusion.
- **Caching**: none — the scale is never cached across runs (platform
  rule); the default view performs two assemblies per render
  (collection + aggregation), the accepted cost of the pure projection.
- **Concurrency**: single-threaded CLI; no shared state beyond the
  hooks run registry (reset per run as today).

## Usages Analysis

### `convention`

- **What it provides**: the project's Python rules — relative imports,
  `kw_only` dataclasses, Google docstrings, CLI docstring rules, test
  structure and naming.
- **Where used**: every touched file; `BoardEntry` (dataclass rules),
  all docstrings, the test files and their names.
- **Why chosen**: mandatory project practice.
- **How exactly**: `from __future__ import annotations`; relative
  intra-package imports (`from ..history import ...`,
  `from ...topics import ...`); `dataclass(frozen=True, kw_only=True)`;
  CLI callbacks keep verbatim-rendered help docstrings without
  Args/Returns/Raises; tests under `tests/topics/`,
  `tests/commands/topics/` named `test_<module>.py`.

### `click`

- **What it provides**: the CLI construction kit and the project's
  click patterns — groups, options, echo, clean errors, `CliRunner`
  testing.
- **Where used**: `topics.board`, `topics.create`, all three renderers,
  the domain's ask/TTY gates.
- **Why chosen**: the declared CLI library of both cells.
- **How exactly**: the repeatable `--host` via `multiple=True` (tuple
  semantics; emptiness tested, never `None`); the optional-value
  `--todo` via `is_flag=False, flag_value=_TODO_DECLARED,
  default=None` with the three-state mapping in the callback and the
  reserved-sentinel rule (verified against click 8.5.0);
  `click.echo` for all output; `click.ClickException` for clean errors;
  `sys.stdin.isatty()` for the interactive gates.

### `beautiful_json`

- **What it provides**: the project's JSON serialization form.
- **Where used**: `render_board_json`.
- **Why chosen**: the manifest connects it for the board's JSON output.
- **How exactly**: `json.dumps(items, indent=4, sort_keys=True,
  ensure_ascii=False)` then one `click.echo` — the trailing newline and
  the plain-stream behavior come from echo.

### Imported Usages

- `topic-board` from `goga/topics` — the board contract of the domain
  (two projections, filter semantics); shapes the `board` callback's
  delegation. Path: `goga/topics/.usages/topic-board.md`.
- `creating` from `goga/topics` — the creation contract with the
  acquisition ladder; shapes the `create` callback's mapping and help
  text. Path: `goga/topics/.usages/creating.md`.
- `editor-entry` from `goga/topics/editor` — the editor session
  protocol the ladder's rung d relies on (cancellation → None; clean
  errors on missing TTY). Path:
  `goga/topics/editor/.usages/editor-entry.md`.
- `topic-paths` from `goga/history` — slug normalization (the
  own-branch equality), year/tree-root patterns.
- `topic-statuses` from `goga/history` — the scale assembly and the
  maximal-status computation the collection and the aggregation's sort
  axis rely on.
- `refs-and-switching` from `goga/topics/git` — the inventory, ref-tree
  reading, and file reading without checkout.
- `publishing` / `deleting` / `switching` / `todo-entry` from
  `goga/topics` — unchanged consumers referenced by the `create` /
  `delete` / `switch` callbacks.
- `project-configuration` from `goga/config` — the topics section
  schema for the lazy base/template resolution.
- `checkpoints` from `goga/config/hooks` — the config amendment
  checkpoint inside `_topics_section` (unchanged).
- `registering-hooks` from `goga/topics` — the lifecycle events the
  command group emits (unchanged; the stdin todo passes through the
  same `amend_creation` checkpoint).

## `.usages/` Update

### Cell: `goga/topics`

#### Existing Files — Consistency

- **`topic-board.md`** → `goga/topics/.usages/topic-board.md`
  - Status: current (updated by the apply stage).
  - Additions needed: none.
  - Updates needed: none — describes both projections, the twin
    collapse, the winner rule, and both filter semantics exactly as
    traced.
- **`creating.md`** → `goga/topics/.usages/creating.md`
  - Status: current (updated by the apply stage).
  - Additions needed: none.
  - Updates needed: none — the ladder, the stdin rules, the
    ask-skip, and the scripted-creation section match the traced
    contract.

### Cell: `goga/commands/topics`

#### Existing Files — Consistency

- **`topics-command.md`** → `goga/commands/topics/.usages/topics-command.md`
  - Status: current (updated by the apply stage).
  - Additions needed: none.
  - Updates needed: none — the board views, the JSON contract, the
    optional-value `--todo`, and the exit codes match the traced
    design. (No usage file states column-width fractions, so the D1
    contract fix has no usage counterpart.)

No new `.usages/` files: the changes stay inside the existing
functional domains (the board and the creation) of both cells; no new
domain appears.

## Test Stack Trace

### General Setup

- Domain board tests (`tests/topics/test_board.py`): the existing
  `_wire_board` monkeypatch harness (scale, `list_branch_refs`,
  `resolve_current_branch_name`, `read_ref_tree_paths`,
  `read_ref_file` patched at their import points in
  `goga.topics.board`) plus the `builtin_scale` fixture; no git binary.
- Domain creation tests (`tests/topics/test_creation.py`): the existing
  repo-in-`tmp_path` harness with the git boundary mocked at the import
  points; the editor mocked (`edit_text` patch point); the hooks
  environment via `recording_hooks`.
- CLI tests (`tests/commands/topics/test_topics.py`): `CliRunner` with
  the domain mocked at its import site in the command module; the
  `_TtyStdin(io.BytesIO)` helper models an interactive stdin; a pinned
  `COLUMNS` keeps the terminal width deterministic.
- Renderer tests (`tests/commands/topics/test_render.py`): plain
  `BoardRecord` / `BoardEntry` instances, `COLUMNS`-independent (the
  width is a direct argument).
- Stdin modeling for the domain tests: monkeypatch `sys.stdin` with
  `io.TextIOWrapper(io.BytesIO(b"..."))` — it exposes `.buffer` and
  reads `isatty()` as False; a `tty` variant subclasses the wrapper
  with `isatty() -> True` to prove the buffer is never read.

### Source File Registry

- `goga/topics/board.py` — `BoardRecord` (wording only),
  `collect_topic_board` (+`hosts`), `BoardEntry` (new),
  `aggregate_topic_board` (new).
- `goga/topics/creation.py` — `create_topic` (+`todo_from_stdin`, the
  ladder), `_resolve_todo` (rewritten), `_publication_asked` (+the
  stdin fact).
- `goga/commands/topics/topics.py` — `board` (new options and views),
  `create` (the option mapping).
- `goga/commands/topics/render.py` — `render_topic_board` (retargeted),
  `render_topic_host_rows` (new name for the moved body),
  `render_board_json` (new).
- `goga/topics/__init__.py`, `goga/commands/topics/__init__.py` — the
  facade exports.

---

### Positive Tests

#### `test_collect_topic_board_filters_records_by_exact_host_names`

**Setup**: `_wire_board` with the base scenario — inventory
`feat/a` (local), `origin/feat/a` (remote), `origin/feat/b` (remote),
`main` (local); trees hosting `feat-a` (plan.md) on `feat/a` and its
twin, `feat-b` (prd.md) on `origin/feat/b`; current `feat/a`; no todo
files.

**Input**: `collect_topic_board(hosts=("main", "origin/feat/b"))`

**Trace**:
```
collect_topic_board(year=None, remote=False, hosts=("main","origin/feat/b"))
  → _board_records: rows built for feat-a@feat/a, feat-b@origin/feat/b
    (main hosts no topic → no row)
  → twin collapse: origin/feat/a dropped (local feat/a wins)
  → hosts filter: {"main", "origin/feat/b"} — feat-a@feat/a dropped
  → sort: feat-b first (scale order: defined precedes planned, so
    feat-b would sort first unfiltered too; the filtered list is
    [feat-b@origin/feat/b] either way)
```

**Assertions**:
```
[(r.topic, r.branch) for r in records] == [("feat-b", "origin/feat/b")]
```

**Sufficiency**: pins the exact display-name equality and the union
across values — a prefix or short-name match would return the twin row
and fail this test.

#### `test_collect_topic_board_empty_hosts_keeps_every_record`

**Setup**: the base scenario.

**Input**: `collect_topic_board(hosts=None)` and
`collect_topic_board(hosts=())`

**Trace**: the filter branch is skipped in both calls → the full
twin-collapsed inventory returns.

**Assertions**:
```
both results equal the unfiltered call: [("feat-b","origin/feat/b"),
("feat-a","feat/a")] (in scale order — defined precedes planned,
as the existing suite pins)
```

**Sufficiency**: the contract's "None or empty keeps every record" —
guards against treating the click `()` default as a filter.

#### `test_aggregate_topic_board_one_entry_per_topic_with_own_branch`

**Setup**: records built directly (no git):
`BoardRecord("feat-a","feat/a",["planned"],True,False,"Fix.")`,
`BoardRecord("feat-a","origin/feat/a",["planned"],False,True,"Fix.")`,
`BoardRecord("release-1-3-0","main",["done"],False,False,None)` —
`main` hosts the merged topic `release-1-3-0` whose own branch is gone,
plus `BoardRecord("release-1-3-0","origin/release/1.3.0",
["done"],False,True,None)` — a remote-tracking own branch.

**Input**: `aggregate_topic_board(records)`

**Trace**:
```
group feat-a → hosts {feat/a} (twin collapsed, local name)
  own: feat/a normalizes to feat-a ✓ (twin also qualifies but loses:
  non-remote wins) → entry branch feat/a
group release-1-3-0 → hosts {main, origin/release/1.3.0}
  own: "main"→"main" ✗; short "release/1.3.0"→"release-1-3-0" ✓
  → entry branch origin/release/1.3.0, remote=True
sort: planned < done? — scale order: done is last; feat-a (planned)
sorts before release-1-3-0 (done)
```

**Assertions**:
```
[(e.topic, e.branch, e.hosts, e.remote) for e in entries] ==
[("feat-a", "feat/a", ["feat/a"], False),
 ("release-1-3-0", "origin/release/1.3.0",
  ["main", "origin/release/1.3.0"], True)]
entries[0].statuses == ["planned"]; entries[0].todo == "Fix."
entries[0].current is True; entries[1].todo is None
```

**Sufficiency**: the core projection — own-branch detection for both
ref kinds, twin collapse in hosts, the merged-host topic keeping its
entry only through its remote own branch.

#### `test_aggregate_topic_board_merged_only_topic_produces_no_entry`

**Setup**: one group: `BoardRecord("old-work","main",["done"],False,
False,None)` — `main` does not normalize to `old-work`.

**Input**: `aggregate_topic_board(records)`

**Trace**: the own-candidate list is empty → the group is skipped; no
other groups exist.

**Assertions**: `entries == []`

**Sufficiency**: the "topic without an own branch produces no entry"
rule — the defining difference of the default view.

#### `test_aggregate_topic_board_own_branch_collision_winner_order`

**Setup**: three parametrized cases over one topic `feature-x` with
own branches colliding — the branch spellings all normalize into the
slug (`Feature X` → `feature-x`, `feature_x` → `feature-x`,
`origin/feature-x` → short `feature-x` → `feature-x`):
(a) `feature_x` (current, non-remote) vs `origin/feature-x` (not
current, remote) → `feature_x` wins;
(b) `Feature X` (not current, non-remote) vs `origin/feature-x`
(remote), neither current → `Feature X` wins;
(c) `feature_x` vs `Feature X`, both non-remote, neither current →
`Feature X` wins (display-name alphabet — uppercase sorts before
lowercase).

**Input**: `aggregate_topic_board(records)` per case.

**Trace**: `min(own, key=(not current, remote, branch))` selects the
declared winner per case; every setup branch is an own-branch
candidate, so the key — not candidate membership — decides.

**Assertions**: `entries[0].branch` equals the expected winner per
case.

**Sufficiency**: the deterministic winner rule — prevents
dict-ordering or input-ordering regressions.

#### `test_aggregate_topic_board_sorts_by_winner_statuses_scale_order`

**Setup**: records built directly, input already in the collection's
order (the least advanced host of each topic first):
`BoardRecord("zzz","zzz",["planned"],False,False,None)`,
`BoardRecord("aaa","aaa",["todo"],False,False,None)` — the own branch —
and `BoardRecord("aaa","z-host",["planned"],False,False,None)` — a
merged host more advanced than the own branch.

**Input**: `aggregate_topic_board(records)` with the input in that
order.

**Trace**: grouping preserves encounter order (zzz, then aaa with the
own record first); the winner of `aaa` is its own-branch record keeping
`["todo"]`; the entry sort re-orders by the winner's first status: todo
precedes planned on the scale → aaa first.

**Assertions**: `[e.topic for e in entries] == ["aaa", "zzz"]`;
`entries[0].statuses == ["todo"]`

**Sufficiency**: proves the output sort is computed from the winner's
statuses (not inherited from the input order — the merged host's
planned would sort aaa last) — the reason the internal scale assembly
exists.

#### `test_aggregate_topic_board_hosts_filter_union_and_no_resurrection`

**Setup**: the merged-host scenario above (feat-a with hosts
`["feat/a"]`, release-1-3-0 with hosts `["main",
"origin/release/1.3.0"]`, plus a merged-only topic old-work on main).

**Input**: `aggregate_topic_board(records, hosts=("main",))`

**Trace**: the own-branch gate runs first (old-work drops); the filter
keeps entries whose hosts contain "main" → release-1-3-0 only.

**Assertions**: `[e.topic for e in entries] == ["release-1-3-0"]`

**Sufficiency**: hosts-membership semantics (a non-own host matches)
and the never-resurrect rule in one pass.

#### `test_aggregate_topic_board_is_read_only_over_records`

**Setup**: the base records list (a snapshot copy taken before).

**Input**: `aggregate_topic_board(records, hosts=("feat/a",))`

**Trace**: grouping and filtering build new lists only.

**Assertions**: `records == snapshot` (element-wise and order).

**Sufficiency**: the read-only requirement — a sort-in-place or
in-place filter regression fails this.

#### `test_aggregate_topic_board_empty_records_yield_empty_list`

**Input**: `aggregate_topic_board([])`

**Trace**: no groups → no entries.

**Assertions**: `entries == []`

**Sufficiency**: the empty-input boundary.

#### `test_board_entry_is_frozen_kw_only_dataclass`

**Setup/Input**: `BoardEntry(topic="t", branch="b", hosts=["h"],
statuses=["todo"], current=False, remote=False, todo=None)`;
`dataclasses.fields(BoardEntry)`; positional construction attempt.

**Trace**: the class shape is inspected directly.

**Assertions**: frozen and kw_only per `is_kw_only_dataclass` (the
shared helper); field order matches the signature; a positional call
raises `TypeError`.

**Sufficiency**: the `convention` data-model rule for the new entity.

#### `test_create_topic_todo_value_wins_over_piped_stdin`

**Setup**: the creation harness; `sys.stdin` monkeypatched to a
`TextIOWrapper(BytesIO(b"piped\n"))` whose `.buffer.read` is wrapped in
a `mock.MagicMock` delegate to count reads.

**Input**: `create_topic("Feature/Foo", "HEAD", todo="Value.",
switch=True)`

**Trace**:
```
preflight passes → ladder rung a: todo truthy → (todo, False)
→ buffer.read never called → no editor → switch path → todo.md written
```

**Assertions**: the buffer-read mock call count is 0; the result line
reports the creation; `todo.md` content is `"Value.\n"`.

**Sufficiency**: "an explicit value wins over piped content; stdin
stays unread" — the first ladder rung.

#### `test_create_topic_todo_from_stdin_with_content`

**Setup**: the creation harness; `sys.stdin` =
`TextIOWrapper(BytesIO(b"First\nSecond\n"))`; `edit_text` patched to a
`MagicMock` (must not be called); `click.confirm` patched (must not be
called).

**Input**: `create_topic("Feature/Foo", "HEAD",
todo_from_stdin=True, switch=True)`

**Trace**:
```
preflight → rung b: non-TTY → one buffer.read → UTF-8 ok →
has_content True → declared → ("First\nSecond\n", True)
→ rung e: switch tolerates → no ask (came_from_stdin) → amendment →
switch path → todo.md written verbatim + one trailing newline
```

**Assertions**: `todo.md` content `"First\nSecond\n"` (already ends
in one newline — kept); `edit_text` not called; `confirm` not called;
the result line is the creation line.

**Sufficiency**: the stdin rung's happy path with the value-form
write semantics and both interaction suppressions.

#### `test_create_topic_publication_ask_skipped_when_todo_came_from_stdin`

**Setup**: the creation harness with a non-TTY stdin —
`TextIOWrapper(BytesIO(b"First\n"))` carrying content; `publish=False`,
`switch=False`; `confirm` patched to a MagicMock that would return
True.

**Input**: `create_topic("Feature/Foo", "HEAD", todo_from_stdin=True)`
(default path)

**Trace**: rung b resolves the stdin todo with `came_from_stdin=True`
→ rung e passes (todo resolved) → the ask gate short-circuits
(came-from-stdin) → the no-switch plant runs.

**Assertions**: `confirm` not called; the quarantined commit exists on
the branch with the stdin todo.

**Sufficiency**: the ask-skip rule — without it the test fails on the
`confirm` call. The test pins the contract outcome (a stdin-sourced
todo never triggers the ask); it cannot isolate the `came_from_stdin`
conjunct alone, because a todo that came from stdin implies the stdin
was non-TTY, so the terminal check would skip the ask too — an
inherent property of the contract, not a test defect.

#### `test_create_topic_amendment_receives_stdin_todo`

**Setup**: the harness + `recording_hooks` subscribing
`amend_creation` and `topic_created`; `sys.stdin` with content.

**Input**: `create_topic("Feature/Foo", "HEAD",
todo_from_stdin=True, switch=True)`

**Trace**: the amendment delivers with `todo` equal to the verbatim
piped text; the notification fires after the write.

**Assertions**: the recorded `amend_creation` context's todo is the
piped text; `topic_created` fired exactly once with `checked_out=True`.

**Sufficiency**: "every todo source — value, stdin, editor — passes
through the same amendment hooks".

#### `test_board_cli_default_view_collects_then_aggregates`

**Setup**: `CliRunner`; in the command module's import scope,
`collect_topic_board` mocked to return `[_record(...)]` and
`aggregate_topic_board` mocked to return `[_entry(...)]`;
`render_topic_board` mocked; `COLUMNS` pinned.

**Input**: `runner.invoke(topics, ["board"])`

**Trace**: the default branch collects without `hosts`, aggregates
with the empty `host` tuple, renders with the entries.

**Assertions**: `collect_topic_board.assert_called_once_with(None,
False)`; `aggregate_topic_board.assert_called_once_with(records,
())` — click's absent `multiple=True` option delivers the empty
tuple, which the domain reads as no filter; `render_topic_board.
assert_called_once()`; exit code 0.

**Sufficiency**: the default-view delegation order — pins that the
projection happens in the domain.

#### `test_board_cli_default_view_passes_host_to_aggregate_only`

**Setup**: as above with `--host feat/a --host main`.

**Input**: `runner.invoke(topics, ["board", "--host", "feat/a",
"--host", "main"])`

**Trace**: click collects `("feat/a", "main")`; the default view
collects unfiltered and aggregates with the tuple.

**Assertions**: `collect_topic_board.assert_called_once_with(None,
False)` (no hosts kwarg); `aggregate_topic_board` called with
`("feat-a".hosts…)` — exactly `(records, ("feat/a", "main"))`.

**Sufficiency**: the two filter semantics route to the right layer —
a record-level pre-filter here would break hosts computation.

#### `test_board_cli_per_host_view_filters_collection`

**Setup**: `collect_topic_board`, `render_topic_host_rows`,
`aggregate_topic_board` mocked in the command module scope.

**Input**: `runner.invoke(topics, ["board", "--per-host", "--host",
"feat/a"])`

**Trace**: the per-host branch passes the filter into the collection
and renders the records.

**Assertions**: `collect_topic_board.assert_called_once_with(None,
False, hosts=("feat/a",))` — the record filter travels as the keyword
argument, matching the traced call shape; `render_topic_host_rows`
called with the records; `aggregate_topic_board` not called.

**Sufficiency**: the audit-view wiring.

#### `test_board_cli_json_prints_aggregated_entries`

**Setup**: `collect_topic_board` + `aggregate_topic_board` mocked;
`aggregate_topic_board` returns one `BoardEntry("feat-a", "feat/a",
["feat/a", "main"], ["planned"], True, False, "Fix.")`.

**Input**: `runner.invoke(topics, ["board", "--json"])`

**Trace**: the JSON branch shapes the entry and serializes.

**Assertions**:
```
json.loads(result.output) == [{"topic": "feat-a", "branch": "feat/a",
  "hosts": ["feat/a", "main"], "statuses": ["planned"],
  "current": True, "remote": False, "todo": "Fix."}]
result.output.startswith("[\n    {")  # indent=4 pretty-printing
exit code 0
```

**Sufficiency**: the stable JSON consumer contract and the
`beautiful_json` formatting.

#### `test_board_cli_json_per_host_records_have_no_hosts_key`

**Setup**: `collect_topic_board` mocked to return one `BoardRecord`;
per-host invocation.

**Input**: `runner.invoke(topics, ["board", "--per-host", "--json"])`

**Trace**: the record branch of the shaper runs.

**Assertions**: `set(json.loads(result.output)[0]) == {"topic",
"branch", "statuses", "current", "remote", "todo"}`.

**Sufficiency**: the per-host record shape — `hosts` absent, `todo`
present.

#### `test_board_cli_json_empty_board_prints_empty_array`

**Setup**: both collectors mocked to return `[]`.

**Input**: `runner.invoke(topics, ["board", "--json"])`

**Assertions**: `result.output == "[]\n"`; exit code 0.

**Sufficiency**: the empty-board JSON boundary.

#### `test_render_topic_board_default_four_columns_with_hosts

**Setup**: one `BoardEntry("feat-a", "feat/a", ["feat/a", "main",
"release/1.3.0"], ["planned"], True, False, "Fix.")`; width 100.

**Input**: `render_topic_board([entry], 100)`

**Trace**: `k=4` → `caps=(22,22,22,22)`; the hosts wrap
("feat/a main release/1.3.0" joined is 26 chars > 22 → two lines:
"feat/a main" + "release/1.3.0"); statuses "[planned]" fits.

**Assertions**:
```
header line == "| Topic | Branch | hosts | Statuses |" padded to caps
the "* feat-a" marker appears in the topic cell
one row divider after the record (the last included)
the hosts cell text spans two grid lines with the earlier columns
empty on the second
len of every line ≤ 100
```

**Sufficiency**: the hosts column, its header, its wrapping, and the
current marker of the new default grid.

#### `test_render_topic_board_info_five_columns_order

**Setup**: the same entry; width 120.

**Input**: `render_topic_board([entry], 120, info=True)`

**Trace**: `k=5` → `caps=(21,21,21,21,21)`; the column order is topic,
branch, hosts, todo, statuses.

**Assertions**: the header cells in order `Topic, Branch, hosts, todo,
Statuses`; the todo cell `"Fix."`; a `None` todo parametrization
renders an empty cell.

**Sufficiency**: the five-column layout and the todo placement between
hosts and statuses.

#### `test_render_topic_board_width_rules_quarter_and_fifth`

**Setup/Input**: parametrized — `render_topic_board([], …)` is not
usable (empty prints nothing); instead call with one entry at widths
100 (default, k=4) and 125 (info, k=5) and measure the printed cell
padding.

**Trace**: `usable(100,4)=88 → 22 each`; `usable(125,5)=110 → 22
each`; below the thresholds (43 with k=4, 54 with k=5) every column is
8 and the table may exceed the width.

**Assertions**: the header separator run lengths equal the computed
caps; at width 43/54 every dash run is 10 (8+2 padding).

**Sufficiency**: pins the corrected D1 fractions through the rendered
grid — the regression the contract fix prevents.

#### `test_render_topic_host_rows_matches_established_layout`

**Setup**: the existing `render_topic_board` record tests' scenarios
(records with wrapped statuses, current marker, info todo).

**Input**: `render_topic_host_rows(records, width[, info])`

**Trace**: the moved body renders exactly as the old board table.

**Assertions**: identical to the current golden expectations of
`test_render.py` (3/4-column grids, "one third"/"one quarter" caps).

**Sufficiency**: the rename must not change the audit layout.

#### `test_create_cli_todo_option_three_states`

**Setup**: `CliRunner`; `create_topic` mocked in the command module
scope; a `tmp_path` cwd without a config file; base via
`--from-current`.

**Input**: `[..."-t", "Text."]`, `[..."--todo"]`, `[... no todo]`,
and `[..."-t", ""]`.

**Trace**: the callback maps the states before the delegation.

**Assertions**:
```
"-t Text."   → create_topic(..., "Text.", False, ...)
"--todo"     → create_topic(..., None, True, ...)
absent       → create_topic(..., None, False, ...)
"-t ''"      → create_topic(..., None, False, ...)
```

**Sufficiency**: the optional-value mapping — the CLI half of the
ladder's front door.

#### `test_create_cli_bare_todo_pipes_stdin_into_domain`

**Setup**: as above with `input=b"First\nSecond\n"` on the runner.

**Input**: `runner.invoke(topics, ["create", "Feature/Foo", "--todo",
"--from-current"], input=b"First\nSecond\n")`

**Trace**: the bare option declares the source; the domain (mocked)
receives the declaration; the real stdin ladder is covered by the
domain tests.

**Assertions**: `create_topic` called with `todo=None,
todo_from_stdin=True`; exit 0.

**Sufficiency**: the end-to-end declaration path through click's
stdin.

---

### Negative Tests

#### `test_create_topic_piped_content_without_declaration_is_clean_error`

**Setup**: `sys.stdin` = `TextIOWrapper(BytesIO(b"piped content\n"))`;
`edit_text` patched (must not run).

**Input**: `create_topic("Feature/Foo", "HEAD")` — no value, no
declaration, non-TTY stdin with content, `switch=True` (so only the
content rule can fail).

**Trace**: rung b — undeclared with content → `click.ClickException`
naming the todo option, before any mutation.

**Assertions**: `pytest.raises(click.ClickException)` with a message
naming `--todo`; the branch was never created (harness assert); the
editor mock not called.

**Sufficiency**: "supplied stdin content is never silently ignored" —
the rule that keeps pipelines honest.

#### `test_create_topic_stdin_non_utf8_is_clean_error`

**Setup**: `sys.stdin` = `TextIOWrapper(BytesIO(b"\xff\xfe\n"))`.

**Input**: `create_topic("Feature/Foo", "HEAD",
todo_from_stdin=True, switch=True)`

**Trace**: the strict decode raises `UnicodeDecodeError`, converted at
the decode site.

**Assertions**: `pytest.raises(click.ClickException)` with a message
naming the todo option; no branch, no directory.

**Sufficiency**: the UTF-8 boundary of the stdin channel — without the
conversion the `ValueError` would pierce the clean-error wrapper.

#### `test_create_topic_headless_no_switch_without_todo_is_local_todo_error`

**Setup**: `sys.stdin` non-TTY with an empty pipe (`BytesIO(b"")`),
no declaration, no value, `switch=False`, `publish=False`.

**Input**: `create_topic("Feature/Foo", "HEAD")`

**Trace**: rung b — undeclared without content → editor rung →
non-interactive → None → rung e — the no-switch path without a todo →
the local-todo clean error.

**Assertions**: `click.ClickException` whose message names the todo
sources and the switch form; nothing mutated.

**Sufficiency**: rung e's no-switch rule (the message now covers the
stdin form too).

#### `test_board_cli_json_with_info_is_clean_error`

**Setup**: `CliRunner`; collectors mocked (must not be called).

**Input**: `runner.invoke(topics, ["board", "--json", "--info"])`

**Trace**: the first algorithm step raises before any collection.

**Assertions**: exit code 1; the error names both flags;
`collect_topic_board` not called.

**Sufficiency**: the mutual exclusion — the todo is always present in
the JSON records.

#### `test_aggregate_topic_board_scale_import_error_is_clean`

**Setup**: `assemble_status_scale` patched at its import point in
`goga.topics.board` to raise `ImportError("broken tool")`; one record.

**Input**: `aggregate_topic_board([record])`

**Trace**: the wrapper converts the fatal assembly failure.

**Assertions**: `pytest.raises(click.ClickException)` with "broken
tool" in the message.

**Sufficiency**: the clean-error boundary of the new routine.

---

### Edge Case Tests

#### `test_create_topic_tty_stdin_never_read`

**Setup**: a stdin wrapper with `isatty() -> True` whose `.buffer` is
a `MagicMock` (any read fails the test); `edit_text` patched to return
"Editor text.".

**Input**: `create_topic("Feature/Foo", "HEAD", switch=True)`

**Trace**: rung c — TTY skips the read; the editor rung resolves the
todo.

**Assertions**: the buffer mock has no reads; `todo.md` content is
`"Editor text.\n"`.

**Sufficiency**: "a terminal stdin is never read" — the guard's
regression test.

#### `test_create_topic_declared_bare_stdin_falls_to_editor`

**Setup**: a TTY stdin model (`isatty() -> True`) whose `.buffer` is a
mock failing the test on any read (the declaration with a TTY stdin
never reads either); `edit_text` patched to return "Typed.".

**Input**: `create_topic("Feature/Foo", "HEAD",
todo_from_stdin=True, switch=True)`

**Trace**: rung c — the TTY skips the read; the declaration finds no
piped content; the editor rung on the interactive terminal resolves
the todo.

**Assertions**: `todo.md` content `"Typed.\n"`.

**Sufficiency**: the bare-declaration fall-through.

#### `test_create_topic_whitespace_only_stdin_counts_as_bare`

**Setup**: the creation harness; `sys.stdin` =
`TextIOWrapper(BytesIO(b"\n  \t\n"))` — non-TTY, whitespace-only
content; `edit_text` patched to a `MagicMock`.

**Input**: `create_topic("Feature/Foo", "HEAD",
todo_from_stdin=True, switch=True)`

**Trace**: rung b — one `buffer.read()` returns `b"\n  \t\n"`; UTF-8
decode succeeds; `content.strip() == ""` → `has_content` False → the
declared+bare case falls through to the editor rung; the editor rung
sees a non-TTY stdin → no todo; rung e — `switch` tolerates the
absent todo; the switch path runs without a todo write.

**Assertions**: `edit_text` not called (the editor rung checks the
terminal first); no `todo.md` file in the topic directory; the result
line reports the creation.

**Sufficiency**: pins the whitespace-only rule of the content test —
a regression to a byte-emptiness check (`data != b""`) would raise the
never-ignored clean error here (the pipe carries non-empty bytes) and
fail this test.

#### `test_aggregate_topic_board_unknown_host_yields_empty`

**Input**: `aggregate_topic_board(records, hosts=("no-such-branch",))`

**Assertions**: `entries == []`; no error.

**Sufficiency**: the unknown-name rule of the entry filter.

#### `test_collect_topic_board_remote_mode_host_filter_uses_remote_names`

**Setup**: `_wire_board` in remote mode (current None), inventory with
`origin/feat/a`.

**Input**: `collect_topic_board(remote=True, hosts=("feat/a",))`

**Trace**: display names are remote-tracking; "feat/a" matches none.

**Assertions**: `records == []`; with `hosts=("origin/feat/a",)` the
row returns.

**Sufficiency**: the filter's display-name semantics under `--remote`.

#### `test_render_board_json_empty_board`

**Input**: `render_board_json([])`

**Assertions**: the output is exactly `"[]\n"` (one trailing newline).

**Sufficiency**: the empty-array boundary and the single trailing
newline.

#### `test_board_cli_empty_board_table_prints_nothing`

**Setup**: both collectors mocked to return `[]`.

**Input**: `runner.invoke(topics, ["board"])` and `[...
"--per-host"]`

**Assertions**: `result.output == ""`; exit code 0.

**Sufficiency**: the empty-board table boundary on both views.

---

## Additional Instructions for the Implementation Agent

- Implement in dependency order: `goga/topics/board.py` (BoardEntry,
  aggregate, hosts filter) → `goga/topics/__init__.py` facade →
  `goga/commands/topics/render.py` (three renderers) →
  `goga/commands/topics/topics.py` (board options, create mapping,
  rewritten help docstrings) → `goga/commands/topics/__init__.py`
  facade.
- `render_topic_host_rows` is the moved body of today's
  `render_topic_board` — move it, retitle the docstring to the audit
  view, keep the mechanics identical.
- Update the module docstrings of `board.py`, `creation.py`,
  `render.py`, `topics.py`, and both `__init__.py` facades to the new
  contracts (they are contract mirrors, not narration).
- Rewrite the `create` callback's help docstring: the value-less
  `--todo` now declares stdin (the old "click's own usage error"
  wording is false); document the three states, the UTF-8 rule, and
  the never-ignored piped content.
- Extend `_LOCAL_TODO_ERROR` to name the stdin source form alongside
  the value form and the switch flag.
- The `--host` option takes no short form (`-h` is click's help);
  `--json` binds to the Python name `json_output`.
- Existing tests needing expectation updates (not deletions):
  `test_facade_exports_two_names` (four names now); the old
  `render_topic_board` record-table tests (they transfer to
  `render_topic_host_rows`); every `create_topic.assert_called_once_
  with(...)` in the CLI tests (the `todo_from_stdin` positional slots
  in after `todo`); `test_board_callback_signature` (the parameter
  list grows to `host`, `per_host`, `json_output`);
  `test_create_bare_todo_flag_is_usage_error` (the value-less `--todo`
  is now a valid declaration — exit 0, not click's usage error);
  `test_board_measures_the_terminal_width` (the default grid is four
  columns now — at COLUMNS 40 the table is 44 wide, at 30 also 44);
  `test_create_todo_option_surface` (its assertions hold on click
  8.5.0, but its docstring and the "no optional-value flag" comment
  must be rewritten to the three-state surface).
- The domain reads stdin exactly once via `sys.stdin.buffer.read()`
  behind the `not sys.stdin.isatty()` guard; decode strictly and
  convert `UnicodeDecodeError` at the site (the wrapper does not
  catch `ValueError`).
- `aggregate_topic_board` assembles the scale internally as the sort
  axis only (see Algorithm Design); wrap its `ImportError` in the
  routine's clean-error boundary.
- Validation gates after implementation: `goga lint` (0 errors),
  `python -c "from goga.topics import BoardEntry,
  aggregate_topic_board"`, `pytest tests/topics tests/commands/topics
  -x`, `ruff check goga/`.
