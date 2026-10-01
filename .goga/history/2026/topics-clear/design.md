# Design Document: `topics-clear`

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/topics/CODEMANIFEST`: header Annotations rewritten onto the pointer model (a topic exists
  exactly as long as its own branch exists, local or remote-tracking; history is communal and is
  never rewritten or deleted); `collect_topic_board` gained the `topics` filter and the primary
  own-branch filter; `aggregate_topic_board` gained the `topics` filter and the remote-mode
  asymmetry requirement; `DeleteTarget.has_dir` became survivor-gated; `resolve_delete_targets`
  step 4 rewritten (branchless topic is a clean error, directory flag survivor-gated); new
  `resolve_clear_targets`; footer Description updated.
- `goga/commands/topics/CODEMANIFEST`: `resolve_clear_targets` added to the `From: goga/topics`
  Imports; header annotations extended (host and topic filters, delete and clear confirmations,
  the clear base ladder); `Subcommand surfaces` extended with `--topic` and the `clear`
  subcommand; `board` method gained the `topic` parameter; new `clear` method; footer updated.
- `goga/commands/CODEMANIFEST`: one annotation sentence of the `topics-command` practice
  enumeration ("the board table with its filters … the deletion and clear flows").
- `goga/topics/git/CODEMANIFEST`: `read_ref_tree_paths` `ref` annotation widened (see Applied
  Fixes).

### New Entities

- `resolve_clear_targets(base_ref: str, year: str | None = None) -> targets: list[DeleteTarget]`
  — `goga/topics`, `location: deletion.py`. Resolves the merged-topic clear scope of one year
  against the base ref's tree into deletion targets; read-only.
- `clear(base_ref: str | None = None, yes: bool = False) -> exit_code: int` — method of the
  `topics` group, `goga/commands/topics`, `location: topics.py`. The `goga topics clear`
  subcommand.

### Changed Entities

- `collect_topic_board` — signature `+ topics: tuple[str, ...] | None = None`; algorithm step 8
  (primary filter: a topic keeps its records only when some ref of the full inventory — both
  local and remote-tracking entries, whatever `remote` mode enumerates — has a branch part that
  normalizes into the topic slug); step 10 composes `hosts` and `topics`; sort moved to step 11.
- `aggregate_topic_board` — signature `+ topics: tuple[str, ...] | None = None`; step 7 composes
  the two filters; new requirement pins the remote-mode asymmetry (a topic whose own branch
  exists only locally keeps its merged-host rows but produces no entry in remote mode).
- `DeleteTarget` — `branch`/`remote` re-documented as the own local branch / own origin twin;
  `has_dir` is survivor-gated: True when the directory exists on disk and no branch surviving
  the deletion carries the topic (the target's own branch is not a gate).
- `resolve_delete_targets` — step 4 rewritten: a topic without its own branch (no ref of the
  inventory whose branch part normalizes into the topic slug) is a clean error; a topic
  directory no branch hosts stays targetable; the directory flag is survivor-gated.
- CLI `topics.board` — `+ topic: tuple[str, ...]` parameter; both filters routed to the domain
  (default view: aggregate; per-host view: collect).

### Deleted Entities

- None.

### Usages and Annotations Changes

- `goga/topics/.usages/topic-board.md` — replaced: pointer-only board (topics without their own
  branch appear in no view), `topics` filter documented, per-host completeness clause dropped.
- `goga/topics/.usages/deleting.md` — replaced: pointer-model deletion semantics, the new
  "Resolving the clear scope of a year" section.
- `goga/commands/topics/.usages/topics-command.md` — extended: `--topic` filter, the
  "Clearing merged topics" section, exit-codes paragraph covers the empty scope and the
  declined confirmation.

## Applied Fixes

### Fixed CODEMANIFEST Defects

- `goga/topics/git/CODEMANIFEST` (`read_ref_tree_paths`): `ref` was "a display branch name as
  carried by `BranchRef`" → now "a display branch name as carried by `BranchRef`, or any
  resolvable revision (a tag, a commit hash) resolved as git resolves it"
  (reason: Interface↔Interface inconsistency — the new `resolve_clear_targets` consumer passes
  `base_ref`, an arbitrary revision; the `git ls-tree` invocation accepts any treeish, but the
  provider contract text did not cover the input domain).
- `goga/topics/CODEMANIFEST` (`resolve_delete_targets`, algorithm step 4): "no hosting ref whose
  name normalizes into the topic slug" → "no ref of the inventory whose branch part normalizes
  into the topic slug" (reason: cross-entity consistency — the own branch is name-based over the
  full inventory everywhere else in the pointer model: `collect_topic_board` step 8,
  `resolve_clear_targets` step 2; the tree-based "hosting" reading diverges in the corner case
  where a branch named after the topic exists but its tree does not carry the topic directory).

Both fixes were approved by the user (option A) and re-validated: `goga lint` — 80 cells,
0 errors; `goga schema` — edges unchanged.

## Entity Interaction and Data Flow

### Interaction Diagram

```
goga/commands (root group)
  └── topics (goga/commands/topics/topics.py, click.Group, --year/-y)
        ├── board  --remote/-r --info/-i --host* --topic* --per-host --json
        │     ├── collect_topic_board(year, remote, [hosts, topics])   → list[BoardRecord]
        │     ├── aggregate_topic_board(records, [hosts, topics])      → list[BoardEntry]
        │     └── render_topic_board | render_topic_host_rows | render_board_json
        ├── create ── create_topic …
        ├── switch ── switch_topic …
        ├── delete ── resolve_delete_targets → confirm → delete_topics
        └── clear   ── _topics_section (load_project_config + ConfigHooks.amend_config)
                      → resolve_clear_targets(base, year) → confirm → delete_topics

goga/topics (domain)
  ├── board.py        BoardRecord, collect_topic_board, BoardEntry, aggregate_topic_board
  ├── deletion.py     DeleteTarget, resolve_delete_targets, resolve_clear_targets, delete_topics
  ├── goga/history    normalize_topic_slug, current_year, collect_history_tree,
  │                   resolve_current_branch_name, resolve_history_root, remove_topic_dir
  └── goga/topics/git list_branch_refs, read_ref_tree_paths, resolve_ref_commit,
                      delete_local_branch, delete_remote_branch, create_branch_at_commit
```

### Data Flows

- **Board, default view**: `board` callback → `collect_topic_board(scope.year, remote)` (no
  display filters — the hosts lists need every hosting branch) → `aggregate_topic_board(records,
  host, topic)` → renderer. The `topic` filter applies at the projection, exactly as `host`.
- **Board, per-host view**: `board` callback → `collect_topic_board(scope.year, remote,
  hosts=host, topics=topic)` → `render_topic_host_rows`. Both display filters apply at the
  collection.
- **Delete**: `delete` callback → `resolve_delete_targets(identifiers, scope.year)` →
  confirmation → `delete_topics(targets, scope.year)` → one result line.
- **Clear**: `clear` callback → base ladder (flag → `topics.base_ref` of the effective
  `ConfigOverlay` → clean error) → `resolve_clear_targets(base, scope.year)` → empty scope
  short-circuits (one line, exit 0) → confirmation → `delete_topics(targets, scope.year)` →
  one result line.
- **Clear resolution internals**: `resolve_clear_targets` → `current_year` → `list_branch_refs`
  → `resolve_ref_commit(base_ref)` (validates resolvability) → `read_ref_tree_paths(commit,
  <history-root>/<year>/)` (base tree topics) → own-branched set from the inventory names →
  scope = intersection → per-topic `DeleteTarget` assembly (own local branch, origin twin,
  survivor-gated `has_dir` via `collect_history_tree` + `read_ref_tree_paths`) →
  current-branch guard.

### Entity Dependencies

Unchanged import graph (verified with `goga schema`): the CLI cell imports
`resolve_clear_targets` inside the existing `From: goga/topics` block — the single new edge;
`goga/commands` → CLI cell unchanged; the domain import set unchanged. No cycles, no
cross-imports. Design order (bottom-up): `goga/topics/git` (wording only) → `goga/topics` →
`goga/commands/topics` → `goga/commands` (annotation only, already materialized).

## Code Stack Trace

### Trace: `collect_topic_board`

#### Chain

1. **Input**: CLI `board` callback (both views), tests. `year: str | None`, `remote: bool`,
   `hosts: tuple[str, ...] | None`, `topics: tuple[str, ...] | None`.
2. Clean-error wrapper catches `subprocess.CalledProcessError` / `FileNotFoundError` /
   `ImportError` → `click.ClickException` → checkpoint: the domain boundary is intact.
3. `_board_records`: `resolved_year = year or current_year()` (str) → checkpoint: `current_year`
   returns 4-digit str, matches the tree path grammar.
4. `scale = assemble_status_scale()` (StatusScale; `ImportError` → clean error) → used by
   `maximal_present` and the sort axis.
5. `inventory = list_branch_refs()` — the FULL inventory (local + remote-tracking), regardless
   of mode; `current = resolve_current_branch_name()` (str | None); mode slices `refs`
   (remote-tracking only under `remote`) → checkpoint: the primary filter must read `inventory`,
   never `refs` — verified: the filter set is built from `inventory`.
6. Per-ref topic trees via `read_ref_tree_paths(ref.name, prefix)` with
   `prefix = <resolve_history_root()>/` → `_year_topics` splits paths into
   `{slug: [artifact...]}` → checkpoint: paths are repo-root-relative posix; `parts[2]` is the
   year; matches the existing grammar.
7. Statuses and todo summaries per row — working copy for the current branch's own topic,
   ref trees otherwise (`read_ref_file`) → unchanged.
8. Twin collapse (`_collapse_remote_twins`) → rows keyed `(slug, branch display name)`.
9. **Primary filter (new)**: `own = {normalize_topic_slug(_short_name(ref.name) if ref.remote
   else ref.name) for ref in inventory} - {""}`; keep only records whose `topic` is in `own` →
   checkpoint: `normalize_topic_slug(str) -> str` (history facade) matches; the branch part rule
   (whole local name, short name after the first `/` for remote-tracking) is the same rule
   `aggregate_topic_board` step 3 uses — type- and logic-verified; a branchless topic passes no
   records in any mode; a topic hosted only by a remote-tracking ref keeps its row (the
   remote-tracking entry normalizes) — existing behavior preserved.
10. Current marking (per row, `_marks_current`) — unchanged; the current branch's OWN topic
    row can never be a dropped row (the current branch is a local ref of the inventory, so
    its slug sits in `own`) — while merged-topic rows hosted by the current branch are marked
    and dropped with their branchless topics, markers and all.
11. **Display filters (extended)**: non-empty `hosts` keeps exact display-name matches
    (union); non-empty `topics` keeps exact slug matches (union); the two compose (AND) →
    checkpoint: filters apply after the primary filter, so they can never resurrect a
    branchless topic.
12. Sort `(scale_order[statuses[0]], topic)` → **Output**: `list[BoardRecord]`, read-only,
    sorted.

#### Checkpoint Summary

- Type flow CLI → domain → renderer: `tuple[str, ...]` options → `tuple[str, ...] | None`
  params → `list[BoardRecord]` → renderer signatures: passed.
- Primary filter semantics vs `aggregate_topic_board` own-branch rule: same name-normalization
  rule over the same inventory: passed.
- Edge: remote mode + own branch local-only → merged-host rows survive the primary filter, the
  projection hides the entry — matches the new aggregate requirement: passed.

### Trace: `aggregate_topic_board`

#### Chain

1. **Input**: CLI `board` (default view), tests. `records: list[BoardRecord]`,
   `hosts: tuple[str, ...] | None`, `topics: tuple[str, ...] | None`.
2. Clean-error wrapper (`ImportError` of the scale assembly only).
3. `_aggregate_board`: scale assembly (sort axis) → group by slug (first-encounter) → hosts
   list per topic → own-branch records via `normalize_topic_slug(_branch_part(record)) == slug`
   → checkpoint: with the collection's primary filter in place, a record set never contains a
   branchless topic's rows in local mode; in remote mode a local-own-branched topic's rows can
   exist without an own-branch row — `own` empty → no entry, per the requirement: passed.
4. Winner selection `(not current, remote, branch)` → entry fields → sort.
5. **Filters (extended)**: non-empty `hosts` — any host in names; non-empty `topics` —
   `entry.topic in slugs`; composed (AND), applied after the own-branch requirement →
   checkpoint: an unknown slug yields `[]`, never an error; no resurrection: passed.
6. **Output**: `list[BoardEntry]`, read-only over `records`, sorted.

#### Checkpoint Summary

- Pure projection — no git access: passed (unchanged).
- Filter order own-branch → display filters: matches the contract's "stands first": passed.

### Trace: `resolve_delete_targets`

#### Chain

1. **Input**: CLI `delete` callback, tests. `identifiers: list[str]`, `year: str | None`.
2. Clean-error wrapper (git failures, missing git, history-tree read OSError).
3. `_resolve_delete_targets`: year → `refs = list_branch_refs()` → `hosted = _hosted_slugs(refs,
   year)` (one `read_ref_tree_paths` per ref under `<root>/<year>/`) → `disk = _disk_slugs(year)`
   (`collect_history_tree`) → checkpoint: all three inventories are read-only and local.
4. Tiers resolve each identifier to one topic slug (exact branch name → exact slug → prefixes);
   ambiguity and no-match are clean errors; identifiers collapse by topic → unchanged.
5. **Assembly (rewritten per target)** — see Algorithm Design `resolve_delete_targets`:
   own-named refs from the inventory; branchless-with-carriers → clean error; directory-only
   stays targetable; survivor-gated `has_dir` → checkpoint: the shared `_assemble_target` is
   also the clear resolver's assembly — one rule, two entry points: passed.
6. `_guard_current_branch` — current branch naming a target's branch or slug → clean error →
   unchanged.
7. **Output**: `list[DeleteTarget]` in identifier order.

#### Checkpoint Summary

- DeleteTarget shape vs `delete_topics` consumption (`branch`, `remote`, `has_dir` fields):
  passed — `delete_topics` is unchanged and already consumes exactly these fields.
- Survivor gate vs `delete_topics` mutation set: the gate excludes exactly the refs the mutation
  deletes (the local branch and the origin twin): passed.
- Behavior deltas pinned by existing tests: the branchless error message changes (no hosting
  branch named); the non-origin-remote-only corner flips `has_dir` to False (see Edge Cases).

### Trace: `resolve_clear_targets` (new)

#### Chain

1. **Input**: CLI `clear` callback, tests. `base_ref: str` (already resolved by the caller —
   flag or configuration), `year: str | None`.
2. Clean-error wrapper — same exception set as `resolve_delete_targets` (`CalledProcessError`,
   `FileNotFoundError`, `OSError`), so an unresolvable base surfaces as
   `click.ClickException(f"git failed: <git reason>")` → checkpoint: "an unresolvable base is a
   clean error carrying the reason" — the `resolve_ref_commit` stderr carries git's own
   message; identical to the `publish_topic` precedent: passed.
3. `resolved_year = year or current_year()` → `refs = list_branch_refs()`.
4. `commit = resolve_ref_commit(base_ref)` — one `git rev-parse --verify <ref>^{commit}`;
   annotated tags peel to commits → checkpoint: `resolve_ref_commit` contract accepts any
   revision string, returns a commit hash: passed.
5. Base tree read: `read_ref_tree_paths(commit, f"{resolve_history_root().as_posix()}/
   {resolved_year}/")` → `_slugs_under` → base topics → checkpoint: after the Applied Fix the
   git-cell contract covers commit hashes; reading at the resolved commit pins one snapshot
   (no double resolution of a moving ref): passed; one git invocation.
6. `own_branched = {_normalized_name(ref) for ref in refs} - {""}` — name-based, tree-free;
   scope = `base_topics & own_branched`, sorted alphabetically → checkpoint: branchless topics
   drop out silently; empty scope → early `[]` return before any per-ref tree read.
7. Non-empty scope → `hosted = _hosted_slugs(refs, resolved_year)`, `disk = _disk_slugs(
   resolved_year)` → `targets = [_assemble_target(topic, refs, hosted, disk) for topic in
   scope]` (shared assembly) → checkpoint: identical `DeleteTarget` semantics for delete and
   clear; several local own branches → the shared clean error: passed.
8. `_guard_current_branch(targets)` → checkpoint: "being the own branch of any target" — the
   guard checks `target.branch == current` (plus the slug arm, unreachable after the
   several-branches error, kept for symmetry): passed.
9. **Output**: `list[DeleteTarget]`, alphabetical by topic, read-only (the base is never moved
   or pushed).

#### Checkpoint Summary

- Caller-supplied `base_ref: str` (CLI resolves None away first) vs signature `str`: passed.
- Read set: 1 rev-parse + 1 base ls-tree + N ref ls-trees + 1 disk walk — the same order as the
  delete resolution: passed.

### Trace: `delete_topics` (unchanged contract, new input semantics)

Consumes `list[DeleteTarget]` from either resolver: capture commit → delete local → delete
origin twin (restore-on-failure) → remove directory iff `has_dir` → emit `topic_deleted` with
the removal composition. No code change; the `has_dir` flag simply carries the survivor-gated
decision. Checkpoint: restore path (`create_branch_at_commit`) and emission are indifferent to
which resolver produced the target: passed.

### Trace: CLI `topics.board` (extended)

1. **Input**: Click-parsed options; `topic: tuple[str, ...]` from the repeatable `--topic`
   option (`multiple=True`, `default=()`).
2. `--json` + `--info` guard (unchanged) → default view: `collect_topic_board(scope.year,
   remote)` then `aggregate_topic_board(records, host, topic)` → per-host view:
   `collect_topic_board(scope.year, remote, hosts=host, topics=topic)` → renderer selection
   unchanged → exit 0 → checkpoint: the `topic` param mirrors the established `host` param
   (declaration order, tuple type, default `()`); filters route exactly per the CODEMANIFEST
   algorithm steps 2–3: passed.

### Trace: CLI `topics.clear` (new)

1. **Input**: `--base-ref` value (str | None), `--yes/-y` flag, the group year scope.
2. Base ladder: `base = base_ref`; `if base is None: section = _topics_section()` (lazy —
   `load_project_config` + `ConfigHooks().amend_config(config=...)`, amendment summary lines to
   stderr, missing file = unset) → `base = section.base_ref`; still None → clean error naming
   the flag and the configuration line, before anything else → checkpoint: "minus the current
   HEAD" — no `--from-current` rung, unlike `create`: passed; `TopicsConfig.base_ref:
   str | None` exists: passed.
3. `targets = resolve_clear_targets(base, scope.year)` — domain errors surface as clean CLI
   errors.
4. Empty scope → `click.echo("No merged topics to clear.")` → exit 0 → checkpoint: one line,
   yearless (the CLI cell imports no year oracle — the domain owns the default): passed.
5. Without `yes`: `sys.stdin.isatty()` probe → non-terminal → clean error; otherwise the
   topic-to-branch pairs (`f"{t.topic} -> {t.branch or t.remote or '(directory only)'}"`) and
   one `click.confirm(f"Clear {len(targets)} topic(s)?")` — declined → exit 0, nothing
   deleted → checkpoint: mirrors `delete` line-for-line; one confirmation for the whole list:
   passed.
6. `line = delete_topics(targets, scope.year)` → `click.echo(line)` → exit 0 → checkpoint:
   `delete_topics(targets, year) -> str` matches: passed.

## Algorithm Design

### `collect_topic_board` (modified)

**Responsibility**: the cross-branch topic inventory of one year — one record per topic and
hosting branch of the own-branched topics; the single source of board facts.

**Algorithm:**
```
1. resolved_year = year or current_year()
2. scale = assemble_status_scale()
3. inventory = list_branch_refs()                # FULL inventory, both kinds
   current = resolve_current_branch_name()
   refs = remote-tracking entries of inventory if remote else inventory
4. per ref: topics_by_ref[ref] = _year_topics(read_ref_tree_paths(ref.name, root_prefix), year)
5. rows[(slug, ref.name)] = (ref.remote, maximal statuses, todo summary)   # working copy
   for the current branch's own topic and its merged topics, ref trees otherwise
6. rows = _collapse_remote_twins(rows)           # the local branch wins
7. own = { normalize_topic_slug(branch_part(ref)) for ref in inventory } - {""}
   where branch_part(ref) = ref.name            if not ref.remote
                          = short_name(ref.name) otherwise
   records = [record for record in records if record.topic in own]        # PRIMARY FILTER
8. records = [ … current=_marks_current(branch, current, remote) … ]
9. IF hosts non-empty: records = [r for r in records if r.branch in set(hosts)]
   IF topics non-empty: records = [r for r in records if r.topic in set(topics)]
10. records.sort(key=(scale_order[first maximal status], topic))
11. return records
```

**Errors:** git infrastructure failures, missing git binary, fatal scale-assembly `ImportError`
→ `click.ClickException` (the existing wrapper).

**Edge Cases:**
- Topic hosted only by a remote-tracking ref → its slug normalizes from the short name → row
  kept in local mode with the remote marker (unchanged behavior, now via the primary filter).
- Remote mode, own branch local-only → the local entry of the full inventory passes the topic
  the primary filter; its merged-host remote rows stay; the projection later hides the entry.
- Own branch exists but its tree carries no topic directory → the topic keeps records carried
  by other hosts (the primary filter is name-based); the aggregated view produces no entry
  (no own-branch record exists) — a documented asymmetry of the same family as the remote-mode
  one.

### `aggregate_topic_board` (modified)

**Responsibility**: pure projection of the per-host records into the default board — exactly
one entry per own-branched topic.

**Algorithm:**
```
1. scale = assemble_status_scale(); scale_order = {stage.name: index}
2. groups = {slug: [records]} (first-encounter order)
3. per slug:
     own = [r for r in group if normalize_topic_slug(_branch_part(r)) == slug]
     IF own is empty: continue                       # no entry, whatever hosts carry it
     winner = min(own, key=(not current, remote, branch))
     entry = BoardEntry(topic, winner.branch, _topic_hosts(group), winner.statuses,
                        winner.current, winner.remote, winner.todo)
4. entries.sort(key=(scale_order[first maximal status], topic))
5. IF hosts non-empty: entries = [e for e in entries if any(h in set(hosts) for h in e.hosts)]
   IF topics non-empty: entries = [e for e in entries if e.topic in set(topics)]
6. return entries
```

**Errors:** fatal scale-assembly `ImportError` → `click.ClickException`.

**Edge Cases:** empty `records` → `[]`; unknown `hosts`/`topics` values → `[]`, never an error;
a filter can never resurrect a topic without an own branch (step 3 precedes step 5).

### `DeleteTarget` (modified data contract)

**Responsibility**: one deletion target — the topic slug, its own local branch (or None), its
own origin twin short name (or None), and the survivor-gated directory flag.

`has_dir` is True exactly when both hold: (a) the topic directory of the year exists on disk;
(b) no branch surviving the deletion carries the topic in its tree. The survivors are the
inventory minus the two refs the deletion removes — the target's own local branch and its
origin twin. A non-origin remote-tracking ref named after the topic (e.g. `upstream/<slug>`)
survives (it is not deletable through origin) and therefore gates the directory like any other
survivor.

### `_assemble_target(topic, refs, hosted, disk)` (rewritten, shared by both resolvers)

**Responsibility**: build one topic's `DeleteTarget` from the full local inventory.

**Algorithm:**
```
1. own_named = [ref for ref in refs if _normalized_name(ref) == topic]
2. IF own_named is empty:
     IF any ref hosts the topic (topic in hosted[ref.name]):
         raise ClickException(f"topic {topic!r} has no branch — "
                              "there is nothing to delete; it is history")
     return DeleteTarget(topic, None, None, has_dir=topic in disk)   # directory-only hygiene
3. local_names = [ref.name for ref in own_named if not ref.remote]
   IF len(local_names) > 1:
     raise ClickException(f"several branches host topic {topic!r}: {names} — "
                          "remove all but one of them before deleting")
4. branch = local_names[0] if local_names else None
   twin = first ref in own_named that is remote and starts with "origin/"
   remote = short_name(twin.name) if twin else None
5. survivors = [ref for ref in refs
                if ref.name != branch and (twin is None or ref.name != twin.name)]
   carried = any(topic in hosted[ref.name] for ref in survivors)
   has_dir = topic in disk and not carried
6. return DeleteTarget(topic, branch, remote, has_dir)
```

**Errors:** branchless-with-carriers → clean error (it is history); several local own branches →
clean error naming them (order-independent).

**Edge Cases:**
- Directory-only topic (no ref hosts it, no ref named after it) → targetable, `has_dir` from
  disk — working-copy hygiene.
- Own branch exists, its tree does not carry the topic, another branch carries it → the branch
  is still the own branch (name-based); `has_dir` False if a survivor carries the topic.
- Topic carried only by a non-origin remote-tracking ref named after it (`upstream/<slug>`) →
  nothing locally deletable (`branch=None`, `remote=None`), and the surviving `upstream` ref
  carries the topic → `has_dir=False`: the deletion is a no-op that still reports and emits its
  event. Deliberate consequence of the survivor-gate letter; the pinned test changes
  accordingly.
- The own branch's own tree carrying the topic does NOT gate the directory (`branch` is excluded
  from survivors — its tree dies with the branch).

### `resolve_delete_targets` (modified)

**Responsibility**: resolve deletion identifiers into targets — every check before any removal.

**Algorithm:**
```
1. resolved_year = year or current_year()
2. refs = list_branch_refs(); hosted = _hosted_slugs(refs, year); disk = _disk_slugs(year)
3. per identifier: _identify(...) through the tiers (exact branch name, exact slug,
   prefixes) — ambiguity / no-match are clean errors; collapse repeated topics
4. targets = [_assemble_target(topic, refs, hosted, disk) for topic in topics]
5. _guard_current_branch(targets)     # current branch naming a target → clean error
6. return targets (identifier order)
```

**Errors:** as the tiers and the assembly above; git/OS failures via the wrapper.

**Edge Cases:** all-or-nothing — any unresolved or ambiguous identifier cancels the whole call;
read-only.

### `resolve_clear_targets` (new)

**Responsibility**: resolve the clear scope of one year against the base ref's tree — every
own-branched topic whose history the base carries — into deletion targets; nothing is removed.

**Algorithm:**
```
1. resolved_year = year or current_year()
2. refs = list_branch_refs()
   own_branched = { _normalized_name(ref) for ref in refs } - {""}
3. commit = resolve_ref_commit(base_ref)
   # unresolvable → CalledProcessError → the wrapper's clean error carrying the git reason
4. year_prefix = f"{resolve_history_root().as_posix()}/{resolved_year}/"
   base_topics = _slugs_under(read_ref_tree_paths(commit, year_prefix), year_prefix)
5. scope = sorted(base_topics & own_branched)
   IF scope is empty: return []
6. hosted = _hosted_slugs(refs, resolved_year); disk = _disk_slugs(resolved_year)
   targets = [_assemble_target(topic, refs, hosted, disk) for topic in scope]
7. _guard_current_branch(targets)
8. return targets (alphabetical by topic)
```

**Errors:** unresolvable base → clean error with the git reason; several local own branches →
the shared assembly error; the current branch being a target's own branch → clean error asking
to switch away first; git/OS failures via the wrapper.

**Edge Cases:**
- Branchless topics (in the base tree but without an own branch) drop out silently.
- The base being the current branch or checked out is not an error — it is only read.
- Empty scope costs 1 rev-parse + 1 base ls-tree — the per-ref tree reads are skipped.
- A topic in scope whose directory on disk is also carried by a surviving branch (e.g. `main`
  still hosting it) → `has_dir=False`: the clear removes the branches, the directory stays.

### `delete_topics` (unchanged)

Consumes targets from either resolver — capture commit, delete local, delete origin twin
(restore on remote failure), remove the directory iff `has_dir`, emit `topic_deleted` per fully
removed target, return one result line. No change.

### CLI `topics.board` (extended)

```
@click.option("--topic", multiple=True, default=(),
              help="Topic slug to keep — an exact match; repeatable, the union across values.")
def board(scope, remote=False, info=False, host=(), per_host=False, json_output=False, topic=()):
    …guard --json+--info…
    if not per_host:
        records = collect_topic_board(scope.year, remote)
        entries = aggregate_topic_board(records, host, topic)
    else:
        records = collect_topic_board(scope.year, remote, hosts=host, topics=topic)
    …render / json… exit 0
```

The callback docstring gains the `--topic` sentence (CLI docstring rule: no Args/Returns/Raises).

### CLI `topics.clear` (new)

```
@topics.command("clear")
@click.option("--base-ref", default=None,
              help="Base whose tree defines the clear scope; beats topics.base_ref of .goga/config.yml.")
@click.option("--yes", "-y", is_flag=True, default=False,
              help="Skip the confirmation; sits after the subcommand token, unlike the group -y year.")
@click.pass_obj
def clear(scope, base_ref=None, yes=False) -> None:
    base = base_ref
    if base is None:
        section = _topics_section()
        base = section.base_ref if section is not None else None
    if base is None:
        raise click.ClickException(
            "no base for the clear — pass --base-ref or set topics.base_ref in .goga/config.yml:\n"
            "topics:\n  base_ref: origin/release/2.0.0")
    targets = resolve_clear_targets(base, scope.year)
    if not targets:
        click.echo("No merged topics to clear.")
        click.get_current_context().exit(0)
    if not yes:
        if not sys.stdin.isatty():
            raise click.ClickException(
                "the clear confirmation needs an interactive terminal — pass --yes/-y to skip it")
        for target in targets:
            click.echo(f"{target.topic} -> {target.branch or target.remote or '(directory only)'}")
        if not click.confirm(f"Clear {len(targets)} topic(s)?"):
            click.get_current_context().exit(0)
    click.echo(delete_topics(targets, scope.year))
    click.get_current_context().exit(0)
```

The `-y` collision with the group `--year` resolves by position, exactly as `delete`.

### Facades

- `goga/topics/__init__.py`: import and re-export `resolve_clear_targets` (deletion import
  block; `__all__` gains it before `resolve_delete_targets`); module docstring gains the
  merged-topic clear scope sentence.
- `goga/commands/topics/__init__.py`: module docstring — "the switching, deletion, and clear
  procedures".

## Cross-cutting Concerns

- **Error handling**: unchanged strategy — the domain wraps `subprocess.CalledProcessError`,
  `FileNotFoundError`, `ImportError`, and `OSError` into `click.ClickException` at each public
  entry; the CLI propagates them as clean stderr errors with exit 1. `resolve_clear_targets`
  joins the same boundary with the same exception set as `resolve_delete_targets`. The
  branchless-topic and unresolvable-base errors are clean errors, never tracebacks.
- **Logging**: none — the domain and CLI report through result lines and clean errors only
  (consistent with the existing cell).
- **Validation**: all-or-nothing inside each resolver (the whole call cancels on any
  unresolved/ambiguous identifier, an unresolvable base, or the current-branch guard); the CLI
  validates its own input combinations before any domain call (no base at all → clean error
  first).
- **Caching**: none — every call reads the inventory live (existing behavior).
- **Concurrency**: not applicable — sequential, single-process CLI flows.
- **Network**: the only network operations remain the deletion pushes inside `delete_topics`;
  both resolvers are strictly local-inventory; no fetch ever happens.

## Usages Analysis

### `convention` (project-level, `.goga/usages/conventions.md`)

- **What it provides**: Python rules — relative imports, `dataclasses` with `kw_only=True`,
  Google-style docstrings, the CLI command docstring rule, the test structure and mock policy
  (mock at import points, real disk via `tmp_path`).
- **Where used**: every changed entity (docstrings of `collect_topic_board`,
  `aggregate_topic_board`, `resolve_clear_targets`, the `clear` callback; the facade exports;
  all tests).
- **Why chosen**: the mandated project practice, referenced by global annotations of every
  touched cell.
- **How exactly**: `resolve_clear_targets` gets a full Google docstring (Args/Returns/
  Algorithm/Requirements/Constraints/Raises); `clear` gets a help docstring without
  Args/Returns/Raises; tests mirror `tests/topics/test_deletion.py` structure.

### `click` (project-level, `.goga/usages/cooks/click.md`)

- **What it provides**: group/command/option construction, repeatable options, `click.confirm`,
  `click.echo`, exit-code propagation, clean-error rendering.
- **Where used**: CLI `board` (new `--topic` option), CLI `clear` (whole subcommand).
- **Why chosen**: the CLI framework practice of the cell.
- **How exactly**: `@click.option("--topic", multiple=True, default=())` mirrors `--host`;
  `--yes/-y` mirrors `delete`; `click.confirm` once for the whole list; `sys.stdin.isatty()`
  for the non-interactive guard.

### `topic-paths`, `topic-statuses` (imported from `goga/history`)

- **What they provide**: the year/tree-root path grammar and the status-scale patterns.
- **Where used**: `collect_topic_board` (unchanged core), `resolve_clear_targets` (year prefix
  composition — same `<root>/<year>/` shape as `_hosted_slugs`).
- **Why chosen / how**: the established inventory-reading patterns; the clear resolution
  reuses `_hosted_slugs` and `_slugs_under` verbatim.

### `refs-and-switching` (imported from `goga/topics/git`)

- **What it provides**: branch inventory, ref-tree reading without checkout, revision
  resolution.
- **Where used**: `collect_topic_board` (primary filter over the inventory), both deletion
  resolvers (`_hosted_slugs`), `resolve_clear_targets` (`resolve_ref_commit` +
  `read_ref_tree_paths` at the resolved commit — covered by the Applied Fix).
- Path: `goga/topics/git/.usages/refs-and-switching.md` — current; no update required (it never
  restricted the ref domain; the CODEMANIFEST is the authoritative widened contract).

### `deleting` (imported from `goga/topics/git`)

- **What it provides**: the symmetric local-and-origin removal and restore-on-failure patterns.
- **Where used**: `delete_topics` (unchanged — consumes the targets of either resolver).

### `deleting` (imported from `goga/topics` — the domain practice)

- **What it provides**: consumer documentation of the deletion and clear contracts.
- **Where used**: CLI `delete`, CLI `clear` annotations.
- Path: `goga/topics/.usages/deleting.md` — current (the "Resolving the clear scope of a year"
  section matches this design's algorithm).

### `topic-board` (imported from `goga/topics`)

- **What it provides**: the board contract for consumers.
- **Where used**: CLI `board`.
- Path: `goga/topics/.usages/topic-board.md` — current (pointer-only semantics, both filters).

### `project-configuration` (imported from `goga/config`), `checkpoints` (imported from `goga/config/hooks`)

- **What they provide**: the topics-section schema (`topics.base_ref`) and the config amendment
  checkpoint delivered at load time.
- **Where used**: CLI `clear` step 1 — the lazy `_topics_section()` helper (load →
  `ConfigHooks().amend_config(config=...)` → effective `ConfigOverlay` → summary lines to
  stderr), identical to `create`.

### `beautiful_json`, `registering-hooks`, `switching`, `creating`, `publishing`, `todo-entry`

Unchanged consumers; referenced by unchanged annotations; no action.

## `.usages/` Update

### Cell: `goga/topics`

- **`topic-board.md`** → current — replaced by the apply-architecture stage; verified against
  this design (filters, primary filter, both examples). No additions.
- **`deleting.md`** → current — the clear-scope section matches the resolved algorithm
  (silent branchless exclusion, read-only base, `DeleteTarget` reuse). No additions.

### Cell: `goga/commands/topics`

- **`topics-command.md`** → current — `--topic` documented; the "Clearing merged topics"
  section matches the CLI algorithm (base ladder, one confirmation, exit codes). No additions.

### Cell: `goga/topics/git`

- **`refs-and-switching.md`** → current — the practice shows the branch-name example and
  imposes no ref-domain restriction; the CODEMANIFEST annotation (post-fix) is the authoritative
  contract. No file change (minimal churn; cookbook: supplement only when a domain changes).

No new `.usages/` files: the clear flow lives inside the existing deletion domain of both
cells.

## Test Stack Trace

### General Setup

- Domain board tests: `_wire_board(monkeypatch, scale, inventory, trees, current, files)` at
  `goga.topics.board`; `builtin_scale` fixture; working-copy topics via `_working_copy_topic` /
  `_working_todo` on `tmp_path` with `monkeypatch.chdir`.
- Domain deletion tests: `_wire_resolution(monkeypatch, inventory, trees, current)` at
  `goga.topics.deletion` (asserts the year prefix); `_disk_topic(tmp_path, year, slug)`; for
  clear additionally patch `resolve_ref_commit` (returns a fixed hash; raises
  `subprocess.CalledProcessError(returncode=128, cmd=..., stderr="fatal: bad revision …")` for
  the unresolvable case).
- CLI tests: `click.testing.CliRunner`, domain functions monkeypatched at
  `goga.commands.topics.topics`; `_TopicsScope(year=…)` via the `--year` group option;
  confirmation flows drive `input="y\n"` / `"n\n"`.

### Source File Registry

- `goga/topics/board.py` — `collect_topic_board`, `aggregate_topic_board`
- `goga/topics/deletion.py` — `DeleteTarget`, `resolve_delete_targets`, `resolve_clear_targets`,
  `delete_topics`
- `goga/topics/__init__.py` — facade exports
- `goga/commands/topics/topics.py` — `board`, `clear`
- `goga/commands/topics/__init__.py` — facade

---

### Positive Tests

#### `test_collect_topic_board_primary_filter_drops_branchless_topics`

**Setup**: `builtin_scale`; inventory `[BranchRef("main", False),
BranchRef("origin/main", True)]`; trees `{"main": [".goga/history/2026/feature-x/plan.md"],
"origin/main": [".goga/history/2026/feature-x/plan.md"]}`; current `"other"` (a branch outside
the inventory is fine — only the name matters); no working-copy topics.

**Input**: `collect_topic_board(year="2026")`.

**Trace**:
```
collect_topic_board(year="2026")
  → _board_records: inventory read; rows built for feature-x on main and origin/main
  → twin collapse: the origin/main row drops — its local twin "main" hosts the
    same topic ((feature-x, "main") is a local key)
  → primary filter: own = {normalize("main"), normalize("main")} = {"main"}
    feature-x not in own → the surviving main row drops too
  → sort of [] → []
```

**Assertions**: `records == []`.

**Sufficiency**: pins the core pointer-model change — a merged-away topic (branch deleted,
history in `main`) appears in no audit view; prevents the primary filter from regressing into
tree-based hosting.

#### `test_collect_topic_board_primary_filter_uses_full_inventory_in_remote_mode`

**Setup**: inventory `[BranchRef("feature-foo", False), BranchRef("origin/main", True)]`;
trees `{"origin/main": [".goga/history/2026/feature-foo/plan.md"]}` (the local branch's tree
carries nothing); current `"feature-foo"`; `remote=True`.

**Input**: `collect_topic_board(year="2026", remote=True)`.

**Trace**:
```
refs = remote-tracking only → [origin/main]
row: (feature-foo, origin/main, ["planned"], current=False, remote=True) — the marker
  would need the own branch's twin origin/feature-foo in the inventory; origin/main's
  short name "main" ≠ the current branch "feature-foo"
primary filter: own from FULL inventory = {"feature-foo", "main"} → feature-foo passes
```

**Assertions**: `[(r.topic, r.branch, r.remote) for r in records] == [("feature-foo",
"origin/main", True)]`.

**Sufficiency**: pins that the primary filter reads the full inventory whatever `remote` mode
enumerates — the asymmetry the aggregate requirement documents.

#### `test_collect_topic_board_topic_filter_union_composition_and_unknown`

**Setup**: `_base_inventory()` + `BranchRef("feat/b", False)` so both topics are own-branched;
`_base_trees()` plus `"feat/b": [".goga/history/2026/feat-b/prd.md"]`.

**Input** (parametrized):
`collect_topic_board(year="2026", topics=("feat-a",))`;
`collect_topic_board(year="2026", topics=("feat-a", "feat-b"))`;
`collect_topic_board(year="2026", hosts=("origin/feat/a",), topics=("feat-b",))`;
`collect_topic_board(year="2026", topics=("nope",))`.

**Trace**:
```
records built (feat-a on feat/a and origin/feat/a; feat-b on feat/b and origin/feat/b)
→ primary filter keeps both (own = {feat-a, feat-b})
→ topics filter: exact slug membership; hosts filter: exact display-name membership; AND
→ unknown slug: no record matches → []
```

**Assertions**: topic sets per case: `{feat-a}`; `{feat-a, feat-b}`; `[]` (feat-b rows sit on
`feat/b`/`origin/feat/b`, host `origin/feat/a` excluded); `[]`.

**Sufficiency**: pins the union-within / AND-across filter algebra and the empty-not-error
rule for the new parameter.

#### `test_aggregate_topic_board_topic_filter_and_no_resurrection`

**Setup**: records built with `_record`: `[("feat-a","feat-a",["planned"]), ("feat-a","main",
["planned"]), ("feat-b","feat-b",["defined"]), ("feat-b","main",["defined"])]`.

**Input** (parametrized): `aggregate_topic_board(records, topics=("feat-a",))`;
`aggregate_topic_board(records, hosts=("main",), topics=("feat-b",))`;
`aggregate_topic_board(records, topics=("ghost",))`.

**Trace**:
```
groups; own-branch records (feat-a→feat-a, feat-b→feat-b); winners; sort
hosts: feat-a = [feat-a, main], feat-b = [feat-b, main]
→ topics filter exact slug; hosts×topics compose AND
→ case 2: feat-b passes both (main in hosts, feat-b in topics) → survives;
  feat-a fails topics → ghost: no entry matches → []
```

**Assertions**: `[e.topic for e in entries]` per case: `["feat-a"]`; `["feat-b"]`; `[]`.

**Sufficiency**: pins the projection-side filter and that a filter never resurrects a
hidden topic.

#### `test_resolve_clear_targets_scope_is_the_intersection`

**Setup**: `monkeypatch.chdir(tmp_path)`; inventory `[BranchRef("feature-foo", False),
BranchRef("origin/feature-foo", True), BranchRef("feature-bar", False),
BranchRef("main", False)]`; trees carrying `feature-foo` and `feature-bar` on their own refs;
`resolve_ref_commit` patched to return `"abc123"`; `read_ref_tree_paths` stand-in answers the
base commit `abc123` with `[".goga/history/2026/feature-foo/prd.md",
".goga/history/2026/other-topic/prd.md"]`; disk: `_disk_topic(tmp_path, "2026", "feature-foo")`;
current `"main"`.

**Input**: `resolve_clear_targets("origin/release/2.0.0", year="2026")`.

**Trace**:
```
own_branched = {feature-foo, feature-bar, main}
base_topics = {feature-foo, other-topic}     # other-topic is branchless
scope = {feature-foo} (sorted)
hosted/disk read → assembly: branch=feature-foo, twin=origin/feature-foo,
  survivors = {feature-bar, main} carry nothing → has_dir=True
guard: main is no target's own branch → pass
```

**Assertions**: `targets == [DeleteTarget(topic="feature-foo", branch="feature-foo",
remote="feature-foo", has_dir=True)]`.

**Sufficiency**: pins the scope intersection, the silent branchless exclusion, the twin
assembly, and the alphabetical single-target order.

#### `test_resolve_clear_targets_survivor_keeps_the_directory`

**Setup**: as above but trees also carry `feature-foo` on `main`
(`"main": [".goga/history/2026/feature-foo/prd.md"]`) and the disk dir exists.

**Input**: `resolve_clear_targets("release/2.0.0", year="2026")`.

**Trace**:
```
scope = {feature-foo}; assembly: survivors = {main} (feature-bar carries nothing)
main carries feature-foo → has_dir=False
```

**Assertions**: `targets[0].has_dir is False` (branch and twin unchanged).

**Sufficiency**: pins the survivor gate inside the clear flow — a merged host still carrying
the topic keeps the working-copy directory.

#### `test_clear_resolves_base_flag_over_configuration_and_delegates`

**Setup**: CliRunner; `goga.commands.topics.topics.resolve_clear_targets` patched to capture
`(base, year)` and return `[DeleteTarget("feature-foo", "feature-foo", "feature-foo", True)]`;
`delete_topics` patched to return `"Deleted 1 topic(s) of 2026: feature-foo"`; `_topics_section`
patched to prove it is NOT called when the flag is given.

**Input**: `runner.invoke(topics, ["--year", "2026", "clear", "--base-ref",
"origin/release/2.0.0", "-y"])`.

**Trace**:
```
clear(base_ref="origin/release/2.0.0", yes=True)
  → base ladder: flag wins, config never read
  → resolve_clear_targets("origin/release/2.0.0", "2026") → 1 target
  → yes → no confirmation
  → delete_topics(targets, "2026") → echo result → exit 0
```

**Assertions**: `result.exit_code == 0`; `"Deleted 1 topic(s)" in result.stdout`;
captured base/year `== ("origin/release/2.0.0", "2026")`; `_topics_section` not called.

**Sufficiency**: pins the flag-beats-configuration ladder and the delegation shape.

#### `test_clear_base_from_configuration_section`

**Setup**: `_topics_section` patched to return `TopicsConfig(base_ref="release/2.0.0",
publish_commit=None)`; domain patched as above (empty scope this time).

**Input**: `runner.invoke(topics, ["clear", "-y"])`.

**Trace**:
```
base_ref None → _topics_section() → base = "release/2.0.0"
→ resolve_clear_targets → [] → echo "No merged topics to clear." → exit 0
```

**Assertions**: `result.exit_code == 0`; `"No merged topics to clear." in result.stdout`;
captured base `== "release/2.0.0"`.

**Sufficiency**: pins the configuration rung and the empty-scope one-line exit-0 path.

#### `test_delete_topics_consumes_clear_targets_end_to_end`

**Setup**: real `delete_topics` with `resolve_ref_commit`/`delete_local_branch`/
`delete_remote_branch`/`remove_topic_dir` patched as recorders; `_disk_topic` created; target
`DeleteTarget("feature-foo", "feature-foo", "feature-foo", True)`.

**Input**: `delete_topics([target], year="2026")`.

**Trace**:
```
capture commit → delete_local_branch("feature-foo") → delete_remote_branch("feature-foo")
→ remove_topic_dir("feature-foo", "2026") → emit topic_deleted
→ "Deleted 1 topic(s) of 2026: feature-foo"
```

**Assertions**: the three removal calls happened in order; the disk dir is gone; the result
line is exact; the event carries the composition (branch, twin, directory_removed=True).

**Sufficiency**: proves the unchanged deletion machinery executes clear-resolved targets
correctly (same type, same flow).

---

### Negative Tests

#### `test_resolve_delete_targets_branchless_topic_is_clean_error`

**Setup**: replaces the body of `test_resolve_delete_targets_merged_topic_is_error`;
inventory `[BranchRef("main", False), BranchRef("origin/main", True)]`; trees carrying
`feature-x` on both; current `"other"`.

**Input**: `resolve_delete_targets(["feature-x"], year="2026")`.

**Trace**:
```
slug tier resolves feature-x (hosted)
→ assembly: own_named empty, main hosts it → ClickException
```

**Assertions**: `pytest.raises(click.ClickException)`; `"has no branch" in message`;
`"nothing to delete" in message`; `"feature-x" in message`; `"main" not in message`.

**Sufficiency**: pins the new branchless error — history is not deletable and the message no
longer names a hosting branch (the old merged-work wording is gone).

#### `test_resolve_clear_targets_unresolvable_base_is_clean_error`

**Setup**: `resolve_ref_commit` patched to raise `subprocess.CalledProcessError(returncode=128,
cmd=["git", …], stderr="fatal: bad revision 'nope'")`; inventory wired.

**Input**: `resolve_clear_targets("nope", year="2026")`.

**Trace**:
```
resolve_ref_commit raises → wrapper catches CalledProcessError
→ ClickException("git failed: fatal: bad revision 'nope'")
```

**Assertions**: `pytest.raises(click.ClickException)`; `"fatal: bad revision" in message`;
nothing deleted (no removal patches invoked).

**Sufficiency**: pins the unresolvable-base clean error carrying the git reason before any
scope work.

#### `test_clear_without_any_base_is_clean_error`

**Setup**: `_topics_section` patched to return `None` (missing config).

**Input**: `runner.invoke(topics, ["clear", "-y"])`.

**Trace**:
```
base_ref None → section None → base None
→ ClickException("no base for the clear — pass --base-ref or set topics.base_ref …")
```

**Assertions**: `result.exit_code == 1`; `"--base-ref" in result.stderr` (via output);
`"topics.base_ref" in output`; `resolve_clear_targets` never called.

**Sufficiency**: pins the base-ladder exhaustion error naming the flag and the configuration
line, before anything else.

#### `test_clear_confirmation_needs_a_terminal`

**Setup**: CliRunner (non-tty stdin by default); `resolve_clear_targets` returns one target;
`yes=False`.

**Input**: `runner.invoke(topics, ["clear", "--base-ref", "origin/main"])`.

**Trace**:
```
targets resolved → not yes → sys.stdin.isatty() False → ClickException
```

**Assertions**: `result.exit_code == 1`; the message names `--yes/-y`; `delete_topics` never
called.

**Sufficiency**: pins the non-interactive guard of the confirmation.

#### `test_resolve_clear_targets_current_branch_guard`

**Setup**: the intersection scenario with current `"feature-foo"` (the own branch of the only
target).

**Input**: `resolve_clear_targets("origin/release/2.0.0", year="2026")`.

**Trace**:
```
scope assembled → _guard_current_branch: target.branch == "feature-foo" → ClickException
```

**Assertions**: `pytest.raises(click.ClickException)`; `"switch away" in message`.

**Sufficiency**: pins the guard — the clear never deletes the checked-out branch.

#### `test_resolve_clear_targets_several_local_own_branches_error`

**Setup**: inventory `[BranchRef("Feature/Foo", False), BranchRef("feature-foo", False)]`;
base tree carries `feature-foo`.

**Input**: `resolve_clear_targets("release/2.0.0", year="2026")`.

**Trace**:
```
own_branched includes feature-foo (both names normalize)
scope = {feature-foo} → assembly: two local own names → ClickException naming both
```

**Assertions**: `"several branches" in message`; both names in the message.

**Sufficiency**: the shared assembly keeps the order-independent ambiguity guard for the clear
flow.

---

### Edge Case Tests

#### `test_resolve_delete_targets_directory_only_stays_targetable`

**Setup**: no trees (nothing hosted); disk has `_disk_topic(tmp_path, "2026", "litter-topic")`;
inventory `[BranchRef("main", False)]`; current `"main"`.

**Input**: `resolve_delete_targets(["litter-topic"], year="2026")`.

**Trace**:
```
slug tier resolves via disk → assembly: own_named empty, no carriers
→ directory-only target: (None, None, has_dir=True)
```

**Assertions**: `targets == [DeleteTarget("litter-topic", None, None, True)]`.

**Sufficiency**: pins the working-copy-hygiene exception to the branchless rule — a topic
directory no branch hosts stays deletable.

#### `test_resolve_delete_targets_own_branch_by_name_without_tree_carriage`

**Setup**: inventory `[BranchRef("feature-foo", False), BranchRef("main", False)]`; trees carry
`feature-foo` on `main` only (the own branch's tree does not); disk has the dir.

**Input**: `resolve_delete_targets(["feature-foo"], year="2026")`.

**Trace**:
```
slug tier resolves (main hosts) → assembly: own_named = [feature-foo] (name-based)
survivors = {main} carries it → has_dir=False
```

**Assertions**: `targets == [DeleteTarget("feature-foo", "feature-foo", None, False)]`.

**Sufficiency**: pins the name-based own-branch rule (the Applied Fix) — the branch enters the
target even when its own tree does not carry the topic.

#### `test_collect_topic_board_own_branch_by_name_without_tree_carriage`

**Setup**: `builtin_scale`; inventory `[BranchRef("feature-foo", False),
BranchRef("main", False)]`; trees `{"main": [".goga/history/2026/feature-foo/plan.md"]}`
(the feature-foo tree carries nothing); current `"main"`; no working-copy topics.

**Input**: `records = collect_topic_board(year="2026")`, then
`aggregate_topic_board(records)`.

**Trace**:
```
own = {feature-foo, main}              # name-based, feature-foo from its branch name
row (feature-foo, main) built          # main hosts the topic in its tree; current-marked
  (main is the current branch — the marked row is a merged-topic row, not an own row)
primary filter: feature-foo ∈ own → the row stays (no own-branch row exists — the
  feature-foo tree is empty, so no (feature-foo, feature-foo) row, no twin collapse)
aggregate: no record whose branch part normalizes into feature-foo → no entry
```

**Assertions**: `[(r.topic, r.branch) for r in records] == [("feature-foo", "main")]`;
`aggregate_topic_board(records) == []`.

**Sufficiency**: pins the name-based own-branch reading on the board side of the Applied
Fix — the records of a topic whose own branch exists by name (but carries no topic
directory in its tree) survive the primary filter while the aggregation produces no
entry; a regression to a tree-based own-branch rule drops the record instead.

#### `test_resolve_delete_targets_non_origin_remote_survivor_gates_directory`

**Setup**: update of `test_resolve_delete_targets_non_origin_remote_is_not_the_twin`;
inventory `[BranchRef("upstream/feature-x", True)]`; trees carry `feature-x` on it; disk has
the dir; current `"main"` (detached from the inventory).

**Input**: `resolve_delete_targets(["feature-x"], year="2026")`.

**Trace**:
```
own_named = [upstream/feature-x] → no local, no origin twin → branch=None, remote=None
survivors = everything (nothing deletable) → upstream carries → has_dir=False
```

**Assertions**: `targets == [DeleteTarget("feature-x", None, None, False)]` (was `has_dir=True`
before — the pinned corner flip).

**Sufficiency**: pins the survivor-gate letter — a non-origin tracking ref survives the
deletion and, carrying the topic, keeps the directory.

#### `test_aggregate_topic_board_remote_mode_local_own_branch_no_entry`

**Setup**: records (as a remote-mode collection would produce):
`[_record("feat-a", "origin/main", ["planned"], remote=True)]` — merged-host row only.

**Input**: `aggregate_topic_board(records)`.

**Trace**:
```
own = records whose branch part normalizes into feat-a → origin/main short name "main" → none
→ no entry
```

**Assertions**: `entries == []`.

**Sufficiency**: pins the new remote-mode asymmetry requirement (rows may exist, no entry).

#### `test_board_default_view_passes_topic_to_aggregate_only`

**Setup**: CliRunner; `goga.commands.topics.topics.collect_topic_board` patched to capture
kwargs and return `[]`; `aggregate_topic_board` patched likewise; renderers patched.

**Input**: `runner.invoke(topics, ["board", "--topic", "feat-a", "--host", "main"])`.

**Trace**:
```
default view: collect(scope.year, remote) — no display filters
aggregate(records, ("main",), ("feat-a",))
```

**Assertions**: collect kwargs exclude `hosts`/`topics`; aggregate kwargs are
`hosts=("main",), topics=("feat-a",)`.

**Sufficiency**: pins the filter routing of the default view (the hosts lists need the full
collection).

#### `test_board_per_host_view_filters_collection_by_topic`

**Setup**: as above.

**Input**: `runner.invoke(topics, ["board", "--per-host", "--topic", "feat-a"])`.

**Trace**:
```
collect(scope.year, remote, hosts=(), topics=("feat-a",))
```

**Assertions**: collect kwargs `hosts=() and topics=("feat-a",)`.

**Sufficiency**: pins the filter routing of the audit view.

#### `test_clear_declined_confirmation_exits_zero`

**Setup**: CliRunner with a tty-simulating stdin (`input="n\n"` plus patched
`sys.stdin.isatty → True`); `resolve_clear_targets` returns one target; `delete_topics`
recorder.

**Input**: `runner.invoke(topics, ["clear", "--base-ref", "origin/main"], input="n\n")`.

**Trace**:
```
pairs printed ("feature-foo -> feature-foo") → confirm "Clear 1 topic(s)?" → n → exit 0
```

**Assertions**: `result.exit_code == 0`; the pair line in output; `delete_topics` not called.

**Sufficiency**: pins the declined-confirmation contract (exit 0, nothing deleted).

#### Contract and surface tests (extend the existing contract classes)

- `test_resolve_clear_targets_signature` — `inspect.signature` matches
  `(base_ref: str, year: str | None = None) -> list[DeleteTarget]`.
- `test_resolve_clear_targets_importable_from_the_cell_facade` —
  `from goga.topics import resolve_clear_targets`; `goga.topics.__all__` contains it.
- `test_board_carries_the_topic_option` / `test_board_callback_signature` — the Click param
  (`multiple=True`) and the callback signature gain `topic: tuple[str, ...] = ()`.
- `test_clear_carries_the_base_ref_option_and_yes_flag` / `test_clear_callback_signature` /
  `test_clear_help_lists_the_surface` — the option surface and the help text (CLI docstring
  rule).
- `test_topics_registers_four_subcommands` → rename to `test_topics_registers_five_subcommands`
  with `["board", "create", "delete", "switch", "clear"]`. `test_facade_exports_four_names`
  stays valid unchanged — `clear` registers on the group; the facade `__all__` keeps its
  four names (three renderers + the group).

**Sufficiency**: keeps the CODEMANIFEST-declared surface pinned test-first, as the existing
classes do.

#### Existing tests to re-pin (behavior deltas of this design)

Every test below was verified against the design's behavior deltas; each needs its
expectations updated before the suite can pass.

`tests/topics/test_deletion.py` — the branchless error message and the name-based
own-branch rule (Applied Fix B):

- `test_resolve_delete_targets_merged_topic_is_error` → branchless message (see the negative
  test above).
- `test_resolve_delete_targets_slug_tier_names_one_topic_of_multi_topic_host` → the same
  branchless message: assert `"has no branch"` / `"feature-b"`; drop the `"merged work"`
  and `"main"` assertions (the new message names no hosting branch).
- `test_resolve_delete_targets_integration_branch_named_directly_is_error` → the same
  replacement: `"cleanup"` stays, `"main"` goes.
- `test_resolve_delete_targets_bare_branch_shadow_reaches_merged_work_guard` → behavior
  flips from a clean error to a resolved target: the bare same-named branch is the own
  branch by name — expect `DeleteTarget("feature-x", "feature-x", None, has_dir=False)`
  (no disk directory; the merged host `main` survives and carries the topic).
- `test_resolve_delete_targets_exact_name_falls_through_bare_branch_to_disk_topic` → the
  target gains the branch: expect `DeleteTarget("feature-foo", "feature-foo", None,
  has_dir=True)` — the bare branch is the topic's own branch under the pointer model; the
  tier fall-through itself is unchanged.
- `test_resolve_delete_targets_non_origin_remote_is_not_the_twin` → `has_dir=False` (see the
  edge test above).

`tests/topics/test_board.py` — the `topics` parameters and the primary filter:

- `test_collect_topic_board_signature` → the parameter list gains `topics` with the
  `tuple[str, ...] | None` hint and the `None` default (mirror `hosts`).
- `test_aggregate_topic_board_signature` → the same for `(records, hosts, topics)`.
- `test_collect_topic_board_current_branch_hosts_merged_topics` → the branchless `feat-b`
  rows drop: keep the scenario by adding a `feat/b` branch to the fixture inventory, or
  assert the dropped rows, per the scenario's intent.
- `test_collect_topic_board_reads_todo_summaries_local_and_ref` → the branchless
  `main-only` row drops under the primary filter: host the `main-only` topic from a ref
  named after it (or drop the row from the expectation and keep the absent-todo coverage
  on an own-branched row).
- `test_collect_topic_board_current_branch_own_topic_wins_over_tree` → the merged `feat-b`
  row on `feat/a` drops: add a `feat/b` ref to the inventory or assert the dropped row.
- Every other board scenario whose inventory carries topics without their own branch →
  add the own branch to the fixture inventory or assert the dropped rows, per the
  scenario's intent.

`tests/commands/topics/test_topics.py`:

- `test_topics_registers_four_subcommands` → rename to `test_topics_registers_five_subcommands`:
  `["board", "create", "delete", "switch", "clear"]` (see the contract tests above).
- `test_board_callback_signature` → the callback parameter list gains `topic` (see the
  contract tests above).

`tests/integration/test_topic_workflows.py` — the pointer model over the real git cell:

- `test_board_standing_on_the_merged_host_keeps_the_topic` → after `branch -d feat-b` the
  branchless topic appears in NO view: the default view keeps only the `feat-a` entry, and
  the `--per-host` audit loses the `(* feat-b, main, …)` row; reword the docstring — the
  board no longer "keeps merged work in view", a branchless topic is history.
- The `legacy-work` scenario (the retired `title.txt` artifact) → the audit row
  `("legacy-work", "legacy", …)` drops under the primary filter (the topic has no branch
  of its own); assert its absence, keep the byte-exact ref-tree assertion.
- `test_delete_merged_topic…` (the branch-deleted merge scenario) → the new branchless
  message: keep `"feature-x"`, drop the `"main"` assertion.
- `test_delete_unpublished_topic_by_exact_name_over_real_git` → the doctrine flip: the
  bare branch is the topic's own branch by name — expect
  `DeleteTarget("feature-foo", "feature-foo", None, has_dir=True)` and assert the branch
  ref is GONE after `delete_topics` (the disk directory still goes with it); reword the
  docstring from "the bare branch stays" to the pointer-model reading.

## Additional Instructions for the Implementation Agent

- Implement strictly bottom-up: `goga/topics/deletion.py` (shared `_assemble_target`,
  `resolve_clear_targets`) → `goga/topics/board.py` (primary filter, `topics` params) →
  `goga/topics/__init__.py` → `goga/commands/topics/topics.py` (`--topic`, `clear`) →
  `goga/commands/topics/__init__.py`.
- Reuse, do not duplicate: `_hosted_slugs`, `_slugs_under`, `_disk_slugs`,
  `_normalized_name`, `_guard_current_branch`, `_short_name` (from `.board`), and the CLI's
  `_topics_section` are shared by both resolvers / both subcommands. One assembly rule — never
  fork a second one.
- The primary filter of `collect_topic_board` reads the FULL `list_branch_refs()` inventory
  (`inventory`), never the mode-sliced `refs`.
- `resolve_clear_targets` reads the base tree at the commit returned by `resolve_ref_commit`
  (one snapshot; a moving ref is not resolved twice). Resolve the base before the per-ref tree
  reads; skip them entirely on an empty scope.
- The clean-error wrappers of `resolve_clear_targets` mirror `resolve_delete_targets`
  (`CalledProcessError`, `FileNotFoundError`, `OSError` → `click.ClickException`).
- Error message texts (keep exact): branchless — `f"topic {topic!r} has no branch — there is
  nothing to delete; it is history"`; several locals — unchanged existing text; no base —
  `"no base for the clear — pass --base-ref or set topics.base_ref in .goga/config.yml:\n"
  "topics:\n  base_ref: origin/release/2.0.0"`; empty clear — `"No merged topics to clear."`;
  confirm — `f"Clear {len(targets)} topic(s)?"`.
- Update the module docstrings of `board.py`, `deletion.py`, `topics.py`, and both `__init__.py`
  facades to the pointer-model wording (Google style; CLI callbacks follow the help-text rule).
- Full gates before done: `pytest tests/ -x` and `ruff check` (could not run in the
  design-stage container — no pytest/ruff; the project venv binaries are macOS-built). Also
  re-run `goga lint` and `goga schema`.
